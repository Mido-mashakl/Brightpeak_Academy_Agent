const loginForm = document.getElementById("loginForm");

const emailInput = document.getElementById("email");

const loginButton = document.getElementById("loginButton");

const errorMessage = document.getElementById("errorMessage");


loginForm.addEventListener("submit", async function (event) {

    event.preventDefault();

    const email = emailInput.value.trim().toLowerCase();

    errorMessage.textContent = "";

    if (!email) {
        errorMessage.textContent = "Please enter your email.";
        return;
    }


    loginButton.disabled = true;

    loginButton.textContent = "LOGGING IN...";


    try {

        const response = await fetch(
            "http://localhost:3000/api/login",
            {
                method: "POST",

                headers: {
                    "Content-Type": "application/json"
                },

                body: JSON.stringify({
                    email: email
                })
            }
        );


        const data = await response.json();
        console.log("LOGIN RESPONSE:", data);


        if (!response.ok) {

            errorMessage.textContent =
                data.message || "Email not found.";

            loginButton.disabled = false;

            loginButton.textContent = "LOGIN";

            return;
        }


        /*
         * نخزن بيانات المستخدم
         * عشان الصفحات التانية تعرف مين دخل
         */

        localStorage.setItem(
            "user",
            JSON.stringify(data.user)
        );


        /*
         * تحديد الصفحة حسب الـ role
         * (روابط مطلقة من روت السيرفر، لأن السيرفر بقى بيسيرف
         * فولدر phase-4 كله عن طريق express.static في server.js)
         */

        if (data.user.role === "student") {
    window.location.href =
        "http://localhost:3000/frontend/student/dashboard/dashboard.html";
}

        else if (data.user.role === "instructor") {

            window.location.href =
                "http://localhost:3000/frontend/instructor/dashboard/dashboard.html";

        }

        else if (data.user.role === "dept_head") {

            window.location.href =
                "http://localhost:3000/frontend/department-head/dashboard/dashboard.html";

        }
else if (data.user.role === "advisor") {
    window.location.href =
        "http://localhost:3000/frontend/advisor/dashboard/dashboard.html";
}

        else {

            errorMessage.textContent =
                "Unknown account role. Please contact support.";

        }

    }

    catch (error) {

        console.error(error);

        errorMessage.textContent =
            "Unable to connect to the server.";

    }


    loginButton.disabled = false;

    loginButton.textContent = "LOGIN";

});