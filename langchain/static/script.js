function speakText(text) {
    let speech = new SpeechSynthesisUtterance(text);
    speech.lang = "en-US";
    speech.rate = 1.05;
    window.speechSynthesis.speak(speech);
}

function sendQuestion(event) {
    event.preventDefault();

    const filename = document.getElementById("filename").value;
    const question = document.getElementById("question").value;

    fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename, question })
    })
    .then(res => res.json())
    .then(data => {
        location.reload();
    });
}
