const startButton = document.getElementById("startButton");

startButton.addEventListener("click", () => {

    startButton.classList.add("clicked");

    setTimeout(() => {
        startButton.classList.remove("clicked");
    }, 300);

});