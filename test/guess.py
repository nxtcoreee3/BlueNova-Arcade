<!-- guess.html -->
<!DOCTYPE html>
<html>
<head>
  <title>BlueNova Python Guess</title>
  <link rel="stylesheet" href="https://pyscript.net/latest/pyscript.css" />
  <script defer src="https://pyscript.net/latest/pyscript.js"></script>
</head>
<body>
  <h2 style="color:#3da9ff;">Python Guessing Game</h2>
  <py-script>
import random

print("Welcome to the Python Guessing Game!")
secret = random.randint(1, 10)
while True:
    guess = int(input("Enter a number (1-10): "))
    if guess == secret:
        print("🎉 Correct!")
        break
    elif guess < secret:
        print("Too low")
    else:
        print("Too high")
  </py-script>
</body>
</html>
