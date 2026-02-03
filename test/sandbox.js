// sandbox test file
// not used in production

function fakeTest(){
  console.log("Running sandbox...");
}

fakeTest();

let values = [1,2,3,4,5];
values.forEach(v=>{
  console.log("Value:",v);
});
