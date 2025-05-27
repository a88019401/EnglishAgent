
async function entryAgent() {

  document.getElementById('loading').style.display = 'block';
  const inputStudentID = document.getElementById("inputStudentID").value;
  const inputPassword = document.getElementById("inputPassword").value;

  const payload = {
    sheetName: "login_data",
    data: [inputStudentID, inputPassword]
  };
    try {
    const res = await fetch("/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const rawText = await res.text();
    if (rawText.error) {
      console.log(rawText.error);
    } else {
      if (rawText === "true")
      {
        sessionStorage.setItem("loginData", JSON.stringify(payload.data));
        window.location.href = `/englishAgent?studentId=${encodeURIComponent(inputStudentID)}`;
      }
      else
      {
        const toastElement = document.querySelector('#toastFail');
        const toastBootstrap = bootstrap.Toast.getOrCreateInstance(toastElement);
        toastBootstrap.show();
      }
      document.getElementById('loading').style.display = 'none';
    }
  } catch (error) {
    console.error(error);
    document.getElementById('loading').style.display = 'none';
  }

}  
async function showToast() {


  if (toastTrigger) {
    console.log("點擊!!!!");
    
    toastTrigger.addEventListener('click', () => {
      console.log("顯示");
      
    })
  }
}
