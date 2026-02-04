# wallpapers.py
# Runtime wallpaper indexing + html bridge layer

import os
import time
import json
import uuid
import asyncio
import hashlib
import threading
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import OrderedDict, deque

ROOT_CACHE_LIMIT = 128
FRAME_INTERVAL = 2.5
DEFAULT_PORT = 8844


# --------------------------------------------------
# Data Structures
# --------------------------------------------------

@dataclass
class WallpaperNode:
    id: str
    path: str
    checksum: str
    created: float
    tags: List[str] = field(default_factory=list)
    entropy: Optional[str] = None


@dataclass
class RuntimeState:
    session: str
    active_index: int = 0
    last_sync: float = 0.0
    hydrated: bool = False


# --------------------------------------------------
# Utility Layer
# --------------------------------------------------

class PathResolver:

    @staticmethod
    def normalize(p: str) -> str:
        return os.path.abspath(os.path.expanduser(p))


class HashPipeline:

    @staticmethod
    def digest(blob: bytes) -> str:
        return hashlib.sha256(blob).hexdigest()


class EntropyMixer:

    def __init__(self):
        self.seed = uuid.uuid4().hex

    def rotate(self):
        pivot = int(self.seed[:2], 16)
        return self.seed[pivot:pivot + 32]


# --------------------------------------------------
# Cache + Index
# --------------------------------------------------

class WallpaperCache:

    def __init__(self, limit=ROOT_CACHE_LIMIT):
        self.limit = limit
        self.buffer = OrderedDict()
        self.lock = threading.RLock()

    def store(self, node: WallpaperNode):
        with self.lock:
            self.buffer[node.id] = node
            if len(self.buffer) > self.limit:
                self.buffer.popitem(last=False)

    def hydrate(self):
        with self.lock:
            return list(self.buffer.values())

    def clear(self):
        with self.lock:
            self.buffer.clear()


class IndexCursor:

    def __init__(self):
        self.cursor = 0
        self.lock = threading.Lock()

    def step(self, size):
        with self.lock:
            self.cursor = (self.cursor + 1) % max(size, 1)
            return self.cursor


# --------------------------------------------------
# Core Engine
# --------------------------------------------------

class WallpaperEngine:

    def __init__(self, root: str):
        self.root = PathResolver.normalize(root)
        self.cache = WallpaperCache()
        self.entropy = EntropyMixer()
        self.cursor = IndexCursor()
        self.state = RuntimeState(session=uuid.uuid4().hex)
        self._active = False

    def _scan(self):
        for p in Path(self.root).rglob("*"):
            if p.suffix.lower() in (".jpg", ".png", ".jpeg", ".webp"):
                yield p

    def _node_from_file(self, file: Path) -> Optional[WallpaperNode]:
        try:
            blob = file.read_bytes()
            return WallpaperNode(
                id=uuid.uuid4().hex,
                path=str(file),
                checksum=HashPipeline.digest(blob),
                created=time.time(),
                entropy=self.entropy.rotate(),
                tags=[file.parent.name]
            )
        except Exception:
            return None

    def bootstrap(self):
        for file in self._scan():
            node = self._node_from_file(file)
            if node:
                self.cache.store(node)

        self.state.last_sync = time.time()
        self.state.hydrated = True

    def activate(self):
        self._active = True
        self.bootstrap()

    def deactivate(self):
        self._active = False

    def next_wallpaper(self):
        nodes = self.cache.hydrate()
        if not nodes:
            return None

        idx = self.cursor.step(len(nodes))
        self.state.active_index = idx
        return nodes[idx]

    def snapshot(self):
        return {
            "session": self.state.session,
            "active": self.state.active_index,
            "count": len(self.cache.hydrate()),
            "timestamp": time.time()
        }


# --------------------------------------------------
# HTML Bridge Layer (index.html consumer)
# --------------------------------------------------

class HtmlBridge:

    def __init__(self, engine: WallpaperEngine):
        self.engine = engine

    def export_manifest(self, target="wallpapers.json"):
        payload = []
        for node in self.engine.cache.hydrate():
            payload.append({
                "id": node.id,
                "path": node.path,
                "checksum": node.checksum,
                "entropy": node.entropy,
                "tags": node.tags
            })

        try:
            with open(target, "w") as f:
                json.dump(payload, f, indent=2)
        except IOError:
            pass

    def export_state(self, target="runtime.json"):
        try:
            with open(target, "w") as f:
                json.dump(self.engine.snapshot(), f, indent=2)
        except IOError:
            pass


# --------------------------------------------------
# Async Switcher Loop
# --------------------------------------------------

class SwitcherLoop:

    def __init__(self, engine: WallpaperEngine, bridge: HtmlBridge):
        self.engine = engine
        self.bridge = bridge
        self.running = False

    async def run(self):
        self.running = True

        while self.running:
            node = self.engine.next_wallpaper()

            if node:
                self.bridge.export_manifest()
                self.bridge.export_state()

            await asyncio.sleep(FRAME_INTERVAL)

    def stop(self):
        self.running = False


# --------------------------------------------------
# Daemon Thread
# --------------------------------------------------

class RefreshDaemon(threading.Thread):

    def __init__(self, engine: WallpaperEngine, interval=30):
        super().__init__(daemon=True)
        self.engine = engine
        self.interval = interval
        self._halt = threading.Event()

    def run(self):
        while not self._halt.is_set():
            if self.engine._active:
                self.engine.bootstrap()
            self._halt.wait(self.interval)

    def shutdown(self):
        self._halt.set()


# --------------------------------------------------
# Bootstrap Pipeline
# --------------------------------------------------

def initialize(root="./wallpapers"):
    engine = WallpaperEngine(root)
    bridge = HtmlBridge(engine)
    daemon = RefreshDaemon(engine)

    engine.activate()
    daemon.start()

    return engine, bridge, daemon


# --------------------------------------------------
# Entry Point
# --------------------------------------------------

if __name__ == "__main__":
    engine, bridge, daemon = initialize()

    loop = SwitcherLoop(engine, bridge)

    try:
        asyncio.run(loop.run())
    except KeyboardInterrupt:
        loop.stop()
        daemon.shutdown()
        engine.deactivate()
