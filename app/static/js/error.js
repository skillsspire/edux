// Простая анимация для логотипа
document.addEventListener("DOMContentLoaded", function () {
    const emoji = document.querySelector('.error-emoji');

    // Простой эффект с увеличением
    let scale = 1;
    setInterval(() => {
        scale = scale === 1 ? 1.2 : 1;
        emoji.style.transform = `scale(${scale})`;
    }, 500);
});

// Мини-игра "Дино"
function startDinoGame() {
    const dino = document.createElement("div");
    dino.style.width = "40px";
    dino.style.height = "40px";
    dino.style.backgroundColor = "green";
    dino.style.position = "absolute";
    dino.style.bottom = "0";
    dino.style.left = "50px";

    const gameArea = document.getElementById("dino-game");
    gameArea.appendChild(dino);

    let dinoJumping = false;

    window.addEventListener("keydown", function (e) {
        if (e.key === " " && !dinoJumping) {
            dinoJumping = true;
            let jumpHeight = 0;
            const jumpInterval = setInterval(function () {
                if (jumpHeight >= 100) {
                    clearInterval(jumpInterval);
                    dinoJumping = false;
                }
                jumpHeight += 5;
                dino.style.bottom = `${jumpHeight}px`;
            }, 20);
        }
    });
}

startDinoGame();
