async function loadStatus() {
  const status = document.querySelector("#status");

  try {
    const response = await fetch("/api/status");
    const data = await response.json();
    status.innerHTML = Object.entries(data)
      .map(([key, value]) => `<div><dt>${key}</dt><dd>${String(value)}</dd></div>`)
      .join("");
  } catch (error) {
    status.innerHTML = `<div><dt>Status</dt><dd>Unavailable</dd></div>`;
  }
}

loadStatus();
