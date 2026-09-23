(() => {
  const $ = (s) => document.querySelector(s);
  const form = $("#form");
  const urlInput = $("#url");
  const goBtn = $("#go");
  const formError = $("#formError");
  const progress = $("#progress");
  const results = $("#results");
  const grid = $("#grid");
  const tpl = $("#cardTpl");

  let pollTimer = null;
  let rendered = 0;

  // ---------- segmented controls
  document.querySelectorAll(".seg").forEach((seg) => {
    seg.addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      seg.querySelectorAll("button").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
    });
  });

  $("#paste").addEventListener("click", async () => {
    try {
      urlInput.value = (await navigator.clipboard.readText()).trim();
      urlInput.focus();
    } catch {
      urlInput.focus();
    }
  });

  $("#again").addEventListener("click", () => {
    stopPolling();
    results.classList.add("hidden");
    progress.classList.add("hidden");
    grid.innerHTML = "";
    urlInput.value = "";
    setBusy(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
    urlInput.focus();
  });

  const isYouTube = (u) => {
    try {
      const h = new URL(u).hostname.toLowerCase();
      return /(^|\.)youtube\.com$/.test(h) || /(^|\.)youtu\.be$/.test(h);
    } catch {
      return false;
    }
  };

  function setBusy(busy) {
    goBtn.disabled = busy;
    urlInput.disabled = busy;
    goBtn.lastChild.textContent = busy ? " Working..." : " Generate Shorts";
  }

  function stopPolling() {
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = null;
  }

  // ---------- submit
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    formError.textContent = "";
    const url = urlInput.value.trim();
    if (!isYouTube(url)) {
      formError.textContent = "Please paste a valid YouTube link (youtube.com or youtu.be).";
      return;
    }
    const len = $("#length .on").dataset;
    const body = {
      url,
      min_len: +len.min,
      max_len: +len.max,
      mode: $("#mode .on").dataset.v,
      quality: +$("#quality").value,
      max_count: +$("#count").value,
      titles: $("#titles .on").dataset.v === "1",
    };

    stopPolling();
    setBusy(true);
    rendered = 0;
    grid.innerHTML = "";
    results.classList.add("hidden");
    $("#zip").classList.add("hidden");
    $("#again").classList.add("hidden");
    progress.className = "card progress";
    $("#srcTitle").textContent = "Preparing...";
    $("#srcThumb").removeAttribute("src");
    setProgress(0, "Starting...");

    try {
      const res = await fetch("/api/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Something went wrong.");
      progress.scrollIntoView({ behavior: "smooth", block: "center" });
      poll(data.job_id);
    } catch (err) {
      progress.classList.add("hidden");
      if (location.protocol === "file:") {
        formError.textContent = "You opened index.html directly. Double-click start.bat and use http://127.0.0.1:5000 instead.";
      } else if (err instanceof TypeError) {
        formError.textContent = "Can't reach the server. Double-click start.bat and keep its black window open while you use the site.";
      } else {
        formError.textContent = err.message;
      }
      setBusy(false);
    }
  });

  function setProgress(pct, stage) {
    $("#barFill").style.width = pct + "%";
    $("#pct").textContent = Math.round(pct) + "%";
    $("#stage").textContent = stage;
  }

  // ---------- polling
  async function poll(jobId) {
    let job;
    try {
      const res = await fetch(`/api/status/${jobId}`);
      job = await res.json();
      if (!res.ok) throw new Error(job.error);
    } catch (err) {
      fail(err.message || "Lost connection to the server.");
      return;
    }

    if (job.title) $("#srcTitle").textContent = job.title;
    if (job.thumbnail && !$("#srcThumb").getAttribute("src")) $("#srcThumb").src = job.thumbnail;
    setProgress(job.progress || 0, job.stage);

    if (job.total) {
      results.classList.remove("hidden");
      $("#count-total").textContent = `of ${job.total}`;
      ensureSkeletons(job.total);
    }
    while (rendered < job.shorts.length) renderShort(jobId, job.shorts[rendered++]);
    $("#count-done").textContent = job.shorts.length;

    if (job.status === "done") {
      progress.classList.add("done");
      $("#count-total").textContent = "";
      grid.querySelectorAll(".skeleton").forEach((s) => s.remove());
      const zip = $("#zip");
      zip.href = `/download-all/${jobId}`;
      zip.classList.remove("hidden");
      $("#again").classList.remove("hidden");
      setBusy(false);
      return;
    }
    if (job.status === "error") {
      fail(job.error || "Processing failed.");
      return;
    }
    pollTimer = setTimeout(() => poll(jobId), 1200);
  }

  function fail(msg) {
    progress.classList.add("error");
    setProgress(100, msg);
    $("#pct").textContent = "!";
    grid.querySelectorAll(".skeleton").forEach((s) => s.remove());
    if (!grid.children.length) results.classList.add("hidden");
    $("#again").classList.remove("hidden");
    setBusy(false);
  }

  function ensureSkeletons(total) {
    const have = grid.children.length;
    for (let i = have; i < total; i++) {
      const card = tpl.content.firstElementChild.cloneNode(true);
      card.classList.add("skeleton");
      card.querySelector("video").remove();
      card.querySelector(".badge").textContent = `#${i + 1}`;
      card.querySelector(".short-title").textContent = `Short ${i + 1}`;
      card.querySelector(".short-range").textContent = "rendering...";
      card.querySelector(".dl").removeAttribute("href");
      card.querySelector(".dl").classList.add("hidden");
      grid.appendChild(card);
    }
  }

  function renderShort(jobId, s) {
    const card = tpl.content.firstElementChild.cloneNode(true);
    const video = card.querySelector("video");
    video.src = `/media/${jobId}/${s.file}`;
    if (s.thumb) video.poster = `/media/${jobId}/${s.thumb}`;
    card.querySelector(".badge").textContent = `#${s.index} · ${fmtDur(s.duration)}`;
    card.querySelector(".short-title").textContent = `Short ${s.index}`;
    card.querySelector(".short-range").textContent = `${s.range} · ${s.size_mb} MB`;
    const dl = card.querySelector(".dl");
    dl.href = `/download/${jobId}/${s.file}`;
    dl.setAttribute("download", s.download_name);

    const slot = grid.children[s.index - 1];
    if (slot && slot.classList.contains("skeleton")) grid.replaceChild(card, slot);
    else grid.appendChild(card);
  }

  const fmtDur = (sec) => {
    sec = Math.round(sec);
    return `${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")}`;
  };
})();
