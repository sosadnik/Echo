const state = {
  health: null,
  settings: null,
  recordings: [],
  jobs: [],
  selectedRecordingId: null,
  selectedJobId: null,
  speakerPrefs: {},
};

const sidebarAppName = document.querySelector("#sidebar-app-name");
const sidebarAppVersion = document.querySelector("#sidebar-app-version");
const sidebarModelName = document.querySelector("#sidebar-model-name");
const sidebarDeviceMode = document.querySelector("#sidebar-device-mode");
const recordingsList = document.querySelector("#recordings-list");
const transcriptEmpty = document.querySelector("#transcript-empty");
const transcriptView = document.querySelector("#transcript-view");
const transcriptSummaryMeta = document.querySelector("#transcript-summary-meta");
const exportTranscriptButton = document.querySelector("#export-transcript-button");
const segmentsList = document.querySelector("#segments-list");
const clipTools = document.querySelector("#clip-tools");
const clipSelectionTitle = document.querySelector("#clip-selection-title");
const clipSelectionMeta = document.querySelector("#clip-selection-meta");
const clipSaveAButton = document.querySelector("#clip-save-a-button");
const clipSaveBButton = document.querySelector("#clip-save-b-button");
const clipClearSelectionButton = document.querySelector("#clip-clear-selection-button");
const clipComparePanel = document.querySelector("#clip-compare-panel");
const clipCompareMeta = document.querySelector("#clip-compare-meta");
const clipPlaySequenceButton = document.querySelector("#clip-play-sequence-button");
const uploadForm = document.querySelector("#upload-form");
const recordingFileInput = document.querySelector("#recording-file");
const uploadSubmitButton = uploadForm.querySelector('button[type="submit"]');
const uploadStatus = document.querySelector("#upload-status");
const clearRecordingsButton = document.querySelector("#clear-recordings-button");
const playerEmpty = document.querySelector("#player-empty");
const playerView = document.querySelector("#player-view");
const playerRecordingName = document.querySelector("#player-recording-name");
const playerRecordingMeta = document.querySelector("#player-recording-meta");
const playerRecordingStatus = document.querySelector("#player-recording-status");
const playerAudioError = document.querySelector("#player-audio-error");
const selectedJobStatus = document.querySelector("#selected-job-status");
const selectedJobUpdated = document.querySelector("#selected-job-updated");
const jobProgressPanel = document.querySelector("#job-progress-panel");
const jobProgressLabel = document.querySelector("#job-progress-label");
const jobProgressPercent = document.querySelector("#job-progress-percent");
const jobProgressTrack = document.querySelector("#job-progress-track");
const jobProgressFill = document.querySelector("#job-progress-fill");
const recordingPlayer = document.querySelector("#recording-player");
const transcribeSelectedButton = document.querySelector("#transcribe-selected-button");
const jobHistory = document.querySelector("#job-history");
const settingsModal = document.querySelector("#settings-modal");
const openSettingsButton = document.querySelector("#open-settings-button");
const closeSettingsButton = document.querySelector("#close-settings-button");
const settingsForm = document.querySelector("#settings-form");
const settingsWhisperModelSelect = document.querySelector("#settings-whisper-model");
const settingsWhisperDeviceSelect = document.querySelector("#settings-whisper-device");
const settingsDiarizationModelInput = document.querySelector("#settings-diarization-model");
const settingsDiarizationDeviceSelect = document.querySelector("#settings-diarization-device");
const settingsTokenState = document.querySelector("#settings-token-state");
const settingsStatus = document.querySelector("#settings-status");
const settingsSubmitButton = document.querySelector("#settings-submit-button");
const themeButtons = Array.from(document.querySelectorAll("[data-theme-option]"));
const clipSlotRefs = {
  A: {
    empty: document.querySelector("#clip-slot-a-empty"),
    content: document.querySelector("#clip-slot-a-content"),
    meta: document.querySelector("#clip-slot-a-meta"),
    text: document.querySelector("#clip-slot-a-text"),
    audio: document.querySelector("#clip-slot-a-audio"),
    playButton: document.querySelector("#clip-slot-a-play-button"),
    clearButton: document.querySelector("#clip-slot-a-clear-button"),
  },
  B: {
    empty: document.querySelector("#clip-slot-b-empty"),
    content: document.querySelector("#clip-slot-b-content"),
    meta: document.querySelector("#clip-slot-b-meta"),
    text: document.querySelector("#clip-slot-b-text"),
    audio: document.querySelector("#clip-slot-b-audio"),
    playButton: document.querySelector("#clip-slot-b-play-button"),
    clearButton: document.querySelector("#clip-slot-b-clear-button"),
  },
};

let refreshInFlight = false;
let uploadInFlight = false;
let cleanupInFlight = false;
let renameInFlight = false;
let settingsSaveInFlight = false;
let exportInFlight = false;
let settingsFormDirty = false;
let activeSegmentIndex = -1;
let modalReturnFocus = null;
let renamingRecordingId = null;
let recordingRenameDraft = "";
const speakerFilterPanelState = {};
const clipSelections = {};
const clipCompareSlots = {
  A: null,
  B: null,
};
const clipBuildState = {
  A: false,
  B: false,
};
let clipSequenceMode = null;

const THEME_STORAGE_KEY = "echo-theme";
const SPEAKER_PREFS_STORAGE_KEY = "echo-speaker-prefs";
const VALID_THEMES = new Set(["light", "dark", "system"]);
const WHISPER_MODEL_OPTIONS = new Set(["tiny", "base", "small", "medium", "large-v3", "turbo"]);

function loadSpeakerPrefs() {
  try {
    const payload = JSON.parse(localStorage.getItem(SPEAKER_PREFS_STORAGE_KEY) || "{}");
    if (payload && typeof payload === "object") {
      return payload;
    }
  } catch (_) {}
  return {};
}

state.speakerPrefs = loadSpeakerPrefs();

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, options);
  } catch (_) {
    throw new Error("Backend niedostępny albo połączenie zostało przerwane.");
  }

  if (!response.ok) {
    const payload = await response.text();
    let message = payload || `Request failed: ${response.status}`;

    try {
      const parsed = JSON.parse(payload);
      message = parsed.detail || parsed.message || message;
    } catch (_) {
      message = payload || message;
    }

    throw new Error(message);
  }

  return response.json();
}

function formatDate(value) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("pl-PL");
}

function formatShortDate(value) {
  if (!value) {
    return "-";
  }
  return new Date(value).toLocaleString("pl-PL", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatTimecode(value) {
  const seconds = Math.max(0, Number(value) || 0);
  const wholeSeconds = Math.floor(seconds);
  const hours = Math.floor(wholeSeconds / 3600);
  const minutes = Math.floor((wholeSeconds % 3600) / 60);
  const secs = wholeSeconds % 60;
  const tenths = Math.floor((seconds - wholeSeconds) * 10);

  const hh = hours ? `${hours}:` : "";
  const mm = hours ? String(minutes).padStart(2, "0") : String(minutes).padStart(2, "0");
  const ss = String(secs).padStart(2, "0");
  const fraction = tenths > 0 ? `.${tenths}` : "";
  return `${hh}${mm}:${ss}${fraction}`;
}

function getModelBadgeLabel(value) {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "-";
  }

  const parts = normalized.split(/[\\/]/).filter(Boolean);
  return parts[parts.length - 1] || normalized;
}

function getDeviceModeLabel(value) {
  const normalized = String(value || "").trim().toLowerCase();
  if (!normalized) {
    return "-";
  }
  return normalized.startsWith("cuda") ? "GPU" : "CPU";
}

function getAllowedWhisperModel(value) {
  const normalized = String(value || "").trim();
  if (WHISPER_MODEL_OPTIONS.has(normalized)) {
    return normalized;
  }
  return "small";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatSegmentCountLabel(count) {
  const value = Math.max(0, Number(count) || 0);
  const mod10 = value % 10;
  const mod100 = value % 100;

  if (value === 1) {
    return "1 segment";
  }
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) {
    return `${value} segmenty`;
  }
  return `${value} segmentów`;
}

function truncateText(value, maxLength = 180) {
  const normalized = String(value || "").replace(/\s+/g, " ").trim();
  if (!normalized || normalized.length <= maxLength) {
    return normalized;
  }
  return `${normalized.slice(0, Math.max(0, maxLength - 1)).trimEnd()}…`;
}

function getClipSelectionIndexes(job) {
  if (!job) {
    return [];
  }

  const rawSelection = Array.isArray(clipSelections[job.id]) ? clipSelections[job.id] : [];
  const normalized = [...new Set(rawSelection
    .map((value) => Number(value))
    .filter((value) => Number.isInteger(value) && value >= 0 && value < job.segments.length))]
    .sort((left, right) => left - right);

  if (normalized.length) {
    clipSelections[job.id] = normalized;
  } else {
    delete clipSelections[job.id];
  }

  return normalized;
}

function getClipSelectionSignature(job) {
  return getClipSelectionIndexes(job).join(",");
}

function toggleClipSelection(job, segmentIndex) {
  if (!job || !Number.isInteger(segmentIndex) || segmentIndex < 0 || segmentIndex >= job.segments.length) {
    return;
  }

  const nextSelection = new Set(getClipSelectionIndexes(job));
  if (nextSelection.has(segmentIndex)) {
    nextSelection.delete(segmentIndex);
  } else {
    nextSelection.add(segmentIndex);
  }

  const normalized = [...nextSelection].sort((left, right) => left - right);
  if (normalized.length) {
    clipSelections[job.id] = normalized;
  } else {
    delete clipSelections[job.id];
  }
}

function clearClipSelection(jobId) {
  if (!jobId) {
    return;
  }

  delete clipSelections[jobId];
}

function getClipSelectionSummary(job, recordingId) {
  const indexes = getClipSelectionIndexes(job);
  if (!job || !indexes.length) {
    return {
      indexes: [],
      ranges: [],
      count: 0,
      duration: 0,
      speakersLabel: "",
      excerpt: "",
    };
  }

  const speakers = [];
  const texts = [];
  let duration = 0;
  const ranges = indexes.map((index) => {
    const segment = job.segments[index];
    const start = Math.max(0, Number(segment?.start) || 0);
    const end = Math.max(start, Number(segment?.end) || start);
    const displaySpeaker = getSpeakerDisplayName(recordingId, segment.speaker);

    duration += Math.max(0, end - start);
    if (displaySpeaker && !speakers.includes(displaySpeaker)) {
      speakers.push(displaySpeaker);
    }

    const text = String(segment?.text || "").trim();
    if (text) {
      texts.push(text);
    }

    return { start, end };
  });

  const visibleSpeakers = speakers.slice(0, 3).join(", ");
  const extraSpeakers = speakers.length > 3 ? ` +${speakers.length - 3}` : "";
  return {
    indexes,
    ranges,
    count: indexes.length,
    duration,
    speakersLabel: `${visibleSpeakers}${extraSpeakers}`.trim(),
    excerpt: truncateText(texts.join(" ")),
  };
}

function revokeClipSlotUrl(slot) {
  if (!slot?.objectUrl) {
    return;
  }

  URL.revokeObjectURL(slot.objectUrl);
}

function clearClipCompareSlot(slotKey) {
  const slot = clipCompareSlots[slotKey];
  if (!slot) {
    return;
  }

  stopClipSequence();
  const refs = clipSlotRefs[slotKey];
  if (refs.audio.dataset.objectUrl === slot.objectUrl) {
    resetClipSlotAudio(refs);
  }
  revokeClipSlotUrl(slot);
  clipCompareSlots[slotKey] = null;
}

function setClipCompareSlot(slotKey, payload) {
  clearClipCompareSlot(slotKey);
  clipCompareSlots[slotKey] = payload;
}

function ensureClipSlotsCompatible(selectedRecording, selectedJob) {
  const recordingId = selectedRecording?.id || null;
  const jobId = selectedJob?.id || null;

  Object.keys(clipCompareSlots).forEach((slotKey) => {
    const slot = clipCompareSlots[slotKey];
    if (!slot) {
      return;
    }

    if (slot.recordingId !== recordingId || slot.jobId !== jobId) {
      clearClipCompareSlot(slotKey);
    }
  });
}

function pauseCompareAudios({ except = null } = {}) {
  Object.entries(clipSlotRefs).forEach(([slotKey, refs]) => {
    if (slotKey === except) {
      return;
    }

    refs.audio.pause();
  });
}

function stopClipSequence() {
  clipSequenceMode = null;
}

function jobStatusLabel(status) {
  switch (status) {
    case "queued":
      return "W kolejce";
    case "running":
      return "Przetwarzanie";
    case "completed":
      return "Gotowe";
    case "failed":
      return "Błąd";
    default:
      return status || "Nieznany";
  }
}

function recordingStatusLabel(status) {
  switch (status) {
    case "ready":
      return "Gotowe";
    case "processing":
      return "Przetwarzanie";
    default:
      return jobStatusLabel(status);
  }
}

function getJobProgressPercent(job) {
  const value = Number(job?.progress_percent);
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.max(0, Math.min(100, Math.round(value)));
}

function getJobProgressMessage(job) {
  const explicit = String(job?.progress_message || "").trim();
  if (explicit) {
    return explicit;
  }

  switch (String(job?.progress_stage || "").trim().toLowerCase()) {
    case "queued":
      return "Job czeka w kolejce.";
    case "starting":
      return "Uruchamianie joba.";
    case "prepare":
      return "Przygotowanie audio.";
    case "whisper":
      return "Whisper przetwarza nagranie.";
    case "diarization":
      return "Diarizacja analizuje speakerów.";
    case "merge":
    case "finalizing":
      return "Finalizacja wyniku.";
    case "completed":
      return "Transkrypcja zakończona.";
    case "failed":
      return job?.error || "Job zakończył się błędem.";
    default:
      return job?.status === "running" ? "Job jest w toku." : "Brak szczegółów postępu.";
  }
}

function getJobDisplayStatus(job) {
  if (!job) {
    return "Brak joba";
  }

  if (job.status === "running" || job.status === "queued") {
    return `${jobStatusLabel(job.status)} ${getJobProgressPercent(job)}%`;
  }

  return jobStatusLabel(job.status);
}

function isJobActive(job) {
  return Boolean(job && (job.status === "queued" || job.status === "running"));
}

function renderProgressMarkup(job, extraClass = "") {
  const percent = getJobProgressPercent(job);
  const message = getJobProgressMessage(job);

  return `
    <div class="recording-progress ${extraClass}">
      <div class="recording-progress-meta">
        <span class="recording-progress-label">${escapeHtml(message)}</span>
        <span class="recording-progress-percent">${percent}%</span>
      </div>
      <div
        class="progress-track"
        role="progressbar"
        aria-label="Postęp przetwarzania"
        aria-valuemin="0"
        aria-valuemax="100"
        aria-valuenow="${percent}"
      >
        <span class="progress-fill" style="width: ${percent}%"></span>
      </div>
    </div>
  `;
}

function hasActiveJobs() {
  return state.jobs.some((job) => job.status === "queued" || job.status === "running");
}

function ensureSelectValue(select, value) {
  if (!value) {
    return;
  }

  const exists = Array.from(select.options).some((option) => option.value === value);
  if (exists) {
    return;
  }

  const option = document.createElement("option");
  option.value = value;
  option.textContent = value;
  select.append(option);
}

function getStoredTheme() {
  try {
    const theme = localStorage.getItem(THEME_STORAGE_KEY);
    if (VALID_THEMES.has(theme)) {
      return theme;
    }
  } catch (_) {}
  return "system";
}

function applyTheme(theme) {
  if (theme === "light" || theme === "dark") {
    document.documentElement.dataset.theme = theme;
  } else {
    delete document.documentElement.dataset.theme;
  }

  themeButtons.forEach((button) => {
    button.classList.toggle("active", button.dataset.themeOption === theme);
  });
}

function saveTheme(theme) {
  if (!VALID_THEMES.has(theme)) {
    return;
  }

  try {
    localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch (_) {}

  applyTheme(theme);
}

function persistSpeakerPrefs() {
  try {
    localStorage.setItem(SPEAKER_PREFS_STORAGE_KEY, JSON.stringify(state.speakerPrefs));
  } catch (_) {}
}

function getRecordingSpeakerPrefs(recordingId) {
  if (!recordingId) {
    return {
      names: {},
      hidden: [],
    };
  }

  const existing = state.speakerPrefs[recordingId];
  if (existing && typeof existing === "object") {
    if (!existing.names || typeof existing.names !== "object") {
      existing.names = {};
    }
    if (!Array.isArray(existing.hidden)) {
      existing.hidden = [];
    }
    return existing;
  }

  const created = {
    names: {},
    hidden: [],
  };
  state.speakerPrefs[recordingId] = created;
  return created;
}

function getSpeakerHiddenSet(recordingId) {
  return new Set(getRecordingSpeakerPrefs(recordingId).hidden);
}

function isSpeakerHidden(recordingId, speaker) {
  return getSpeakerHiddenSet(recordingId).has(speaker);
}

function getSpeakerDisplayName(recordingId, speaker) {
  return getRecordingSpeakerPrefs(recordingId).names[speaker] || speaker;
}

function getSpeakerNameOverrides(recordingId) {
  return Object.fromEntries(
    Object.entries(getRecordingSpeakerPrefs(recordingId).names || {}).flatMap(([speaker, displayName]) => {
      const normalizedSpeaker = String(speaker || "").trim();
      const normalizedDisplayName = String(displayName || "").trim();
      if (!normalizedSpeaker || !normalizedDisplayName) {
        return [];
      }
      return [[normalizedSpeaker, normalizedDisplayName]];
    }),
  );
}

function getSpeakerPrefsSignature(recordingId) {
  if (!recordingId) {
    return "";
  }

  const prefs = getRecordingSpeakerPrefs(recordingId);
  const names = Object.entries(prefs.names || {}).sort(([left], [right]) => left.localeCompare(right, "pl"));
  const hidden = [...new Set(prefs.hidden || [])].sort((left, right) => left.localeCompare(right, "pl"));
  return JSON.stringify({ names, hidden });
}

function setSpeakerHidden(recordingId, speaker, hidden) {
  if (!recordingId || !speaker) {
    return;
  }

  const prefs = getRecordingSpeakerPrefs(recordingId);
  const hiddenSet = new Set(prefs.hidden);

  if (hidden) {
    hiddenSet.add(speaker);
  } else {
    hiddenSet.delete(speaker);
  }

  prefs.hidden = [...hiddenSet].sort((left, right) => left.localeCompare(right, "pl"));
  persistSpeakerPrefs();
}

function renameSpeaker(recordingId, speaker) {
  if (!recordingId || !speaker) {
    return;
  }

  const currentName = getSpeakerDisplayName(recordingId, speaker);
  const nextName = window.prompt(
    "Nowa nazwa speakera. Zostaw puste pole, aby wrócić do nazwy oryginalnej.",
    currentName,
  );

  if (nextName === null) {
    return;
  }

  const normalized = nextName.trim();
  const prefs = getRecordingSpeakerPrefs(recordingId);

  if (!normalized || normalized === speaker) {
    delete prefs.names[speaker];
  } else {
    prefs.names[speaker] = normalized;
  }

  persistSpeakerPrefs();
  renderAll();
}

function getSpeakerEntries(job, recordingId) {
  const entries = new Map();

  job.segments.forEach((segment, index) => {
    if (!entries.has(segment.speaker)) {
      entries.set(segment.speaker, {
        rawSpeaker: segment.speaker,
        count: 0,
        firstIndex: index,
      });
    }

    const current = entries.get(segment.speaker);
    current.count += 1;
  });

  return Array.from(entries.values())
    .map((entry) => ({
      ...entry,
      displayName: getSpeakerDisplayName(recordingId, entry.rawSpeaker),
      hidden: isSpeakerHidden(recordingId, entry.rawSpeaker),
    }))
    .sort((left, right) => left.firstIndex - right.firstIndex);
}

function getVisibleSegments(job, recordingId) {
  const hiddenSpeakers = getSpeakerHiddenSet(recordingId);
  return job.segments.flatMap((segment, index) => {
    if (hiddenSpeakers.has(segment.speaker)) {
      return [];
    }

    return [{
      segment,
      index,
      displayName: getSpeakerDisplayName(recordingId, segment.speaker),
    }];
  });
}

function getRecordingJobs(recordingId) {
  return state.jobs
    .filter((job) => job.recording_id === recordingId)
    .sort((left, right) => Date.parse(right.created_at) - Date.parse(left.created_at));
}

function getActiveJob(recordingId) {
  return getRecordingJobs(recordingId).find((job) => isJobActive(job)) || null;
}

function getSelectedRecording() {
  return state.recordings.find((recording) => recording.id === state.selectedRecordingId) || null;
}

function getSelectedJob() {
  return state.jobs.find((job) => job.id === state.selectedJobId) || null;
}

function getRecordingById(recordingId) {
  return state.recordings.find((recording) => recording.id === recordingId) || null;
}

function resetRecordingRename() {
  renamingRecordingId = null;
  recordingRenameDraft = "";
}

function focusRecordingRenameInput(recordingId) {
  window.requestAnimationFrame(() => {
    const input = recordingsList.querySelector(`[data-recording-rename-input="${recordingId}"]`);
    if (!(input instanceof HTMLInputElement)) {
      return;
    }

    input.focus();
    input.select();
  });
}

function startRecordingRename(recordingId) {
  const recording = getRecordingById(recordingId);
  if (!recording || renameInFlight || uploadInFlight || cleanupInFlight) {
    return;
  }

  renamingRecordingId = recordingId;
  recordingRenameDraft = recording.original_name || "";
  renderAll();
  focusRecordingRenameInput(recordingId);
}

function cancelRecordingRename() {
  if (renameInFlight) {
    return;
  }

  resetRecordingRename();
  renderAll();
}

function syncSelection() {
  if (!state.recordings.length) {
    state.selectedRecordingId = null;
    state.selectedJobId = null;
    return;
  }

  const selectedJob = state.jobs.find((job) => job.id === state.selectedJobId);
  if (selectedJob && selectedJob.recording_id !== state.selectedRecordingId) {
    state.selectedRecordingId = selectedJob.recording_id;
  }

  if (!state.recordings.some((recording) => recording.id === state.selectedRecordingId)) {
    state.selectedRecordingId = selectedJob?.recording_id || state.recordings[0].id;
  }

  const jobsForRecording = getRecordingJobs(state.selectedRecordingId);
  const selectedRecording = getSelectedRecording();
  if (!jobsForRecording.some((job) => job.id === state.selectedJobId)) {
    const preferredJob = selectedRecording?.status === "processing"
      ? jobsForRecording.find((job) => isJobActive(job)) || jobsForRecording.find((job) => job.status === "completed")
      : jobsForRecording.find((job) => job.status === "completed") || jobsForRecording[0];
    state.selectedJobId = preferredJob?.id || null;
  }
}

function getRecordingSummary(recording) {
  const jobs = getRecordingJobs(recording.id);
  const latestJob = jobs[0] || null;
  const activeJob = getActiveJob(recording.id);

  if (recording.status === "processing") {
    return {
      tone: activeJob?.status || "running",
      label: activeJob ? getJobDisplayStatus(activeJob) : "Przetwarzanie",
      detail: activeJob ? getJobProgressMessage(activeJob) : "Trwa aktywny job.",
      progressJob: activeJob,
    };
  }

  if (!latestJob) {
      return {
        tone: "ready",
        label: "Bez transkrypcji",
        detail: "Gotowe do uruchomienia.",
        progressJob: null,
      };
    }

  if (latestJob.status === "completed") {
      return {
        tone: "completed",
        label: "Transkrypcja gotowa",
        detail: latestJob.segments.length
          ? `${latestJob.segments.length} segmentów mówców.`
          : "Brak segmentów w wyniku.",
        progressJob: null,
      };
    }

  if (latestJob.status === "failed") {
      return {
        tone: "failed",
        label: "Błąd joba",
        detail: latestJob.error || "Ostatnia próba zakończyła się błędem.",
        progressJob: null,
      };
    }

  return {
    tone: latestJob.status,
    label: getJobDisplayStatus(latestJob),
    detail: getJobProgressMessage(latestJob),
    progressJob: latestJob,
  };
}

function renderStatus() {
  sidebarAppName.textContent = state.settings?.app_name || "Echo";
  sidebarAppVersion.textContent = state.settings?.app_version || "-";

  if (!state.settings) {
    sidebarModelName.textContent = state.health ? "-" : "Offline";
    sidebarDeviceMode.textContent = "-";
    return;
  }

  sidebarModelName.textContent = getModelBadgeLabel(state.settings.whisper_model);
  sidebarDeviceMode.textContent = getDeviceModeLabel(state.settings.whisper_device);
}

function renderSettingsForm({ force = false } = {}) {
  const settings = state.settings;
  const activeJobs = hasActiveJobs();
  settingsSubmitButton.disabled = !settings || settingsSaveInFlight || uploadInFlight || cleanupInFlight || activeJobs;

  if (!settings) {
    settingsTokenState.textContent = "HF token: brak danych z backendu";
    return;
  }

  const tokenState = settings.huggingface_token_configured ? "HF token: OK" : "HF token: brak";
  settingsTokenState.textContent = activeJobs
    ? `${tokenState} | aktywny job blokuje zapis konfiguracji`
    : tokenState;

  if (settingsFormDirty && !force) {
    return;
  }

  settingsWhisperModelSelect.value = getAllowedWhisperModel(settings.whisper_model);
  ensureSelectValue(settingsWhisperDeviceSelect, settings.whisper_device || "cpu");
  settingsWhisperDeviceSelect.value = settings.whisper_device || "cpu";
  settingsDiarizationModelInput.value = settings.diarization_model || "";
  ensureSelectValue(settingsDiarizationDeviceSelect, settings.diarization_device || settings.whisper_device || "cpu");
  settingsDiarizationDeviceSelect.value = settings.diarization_device || settings.whisper_device || "cpu";
}

function setUploadStatus(message, tone = "neutral") {
  if (!message) {
    uploadStatus.textContent = "";
    uploadStatus.className = "upload-status hidden";
    return;
  }

  uploadStatus.textContent = message;
  uploadStatus.className = "upload-status";
  if (tone === "error") {
    uploadStatus.classList.add("error");
  }
  if (tone === "success") {
    uploadStatus.classList.add("success");
  }
}

function setSettingsStatus(message, tone = "neutral") {
  if (!message) {
    settingsStatus.textContent = "";
    settingsStatus.className = "settings-status hidden";
    return;
  }

  settingsStatus.textContent = message;
  settingsStatus.className = "settings-status";
  if (tone === "error") {
    settingsStatus.classList.add("error");
  }
  if (tone === "success") {
    settingsStatus.classList.add("success");
  }
}

function setPlayerAudioError(message) {
  if (!message) {
    playerAudioError.textContent = "";
    playerAudioError.classList.add("hidden");
    return;
  }

  playerAudioError.textContent = message;
  playerAudioError.classList.remove("hidden");
}

function readXhrPayload(request) {
  if (request.response && typeof request.response === "object") {
    return request.response;
  }

  if (!request.responseText) {
    return null;
  }

  try {
    return JSON.parse(request.responseText);
  } catch (_) {
    return request.responseText;
  }
}

function renderRecordingSpeakerFilters(recordingId) {
  if (!recordingId || recordingId !== state.selectedRecordingId) {
    return "";
  }

  const selectedJob = getSelectedJob();
  if (
    !selectedJob
    || selectedJob.recording_id !== recordingId
    || selectedJob.status !== "completed"
    || !selectedJob.segments.length
  ) {
    return "";
  }

  const speakerEntries = getSpeakerEntries(selectedJob, recordingId);
  if (!speakerEntries.length) {
    return "";
  }

  const isOpen = speakerFilterPanelState[recordingId] ?? true;
  return `
    <details class="recording-speaker-filters" data-action="speaker-filters-panel" ${isOpen ? "open" : ""}>
      <summary class="recording-speaker-summary">Filtry speakerów</summary>
      <div class="recording-speaker-list">
        ${speakerEntries.map((entry) => `
          <div class="recording-speaker-item ${entry.hidden ? "is-hidden" : ""}">
            <input
              class="recording-speaker-checkbox"
              type="checkbox"
              data-action="toggle-speaker"
              data-speaker="${escapeHtml(entry.rawSpeaker)}"
              aria-label="Pokaż speakera ${escapeHtml(entry.displayName)}"
              ${entry.hidden ? "" : "checked"}
            >
            <button
              type="button"
              class="speaker-name-button recording-speaker-name"
              data-action="rename-speaker"
              data-speaker="${escapeHtml(entry.rawSpeaker)}"
            >
              ${escapeHtml(entry.displayName)}
            </button>
          </div>
        `).join("")}
      </div>
    </details>
  `;
}

function renderRecordings() {
  const hasRecordings = state.recordings.length > 0;
  const hasProcessing = state.recordings.some((recording) => recording.status === "processing");
  clearRecordingsButton.disabled = !hasRecordings || hasProcessing || cleanupInFlight || uploadInFlight || renameInFlight;

  if (!hasRecordings) {
    recordingsList.className = "recordings-list empty";
    recordingsList.textContent = "Brak nagrań.";
    return;
  }

  recordingsList.className = "recordings-list";
  recordingsList.innerHTML = state.recordings.map((recording) => {
    const summary = getRecordingSummary(recording);
    const isSelected = recording.id === state.selectedRecordingId;
    const isRenaming = recording.id === renamingRecordingId;
    const busy = recording.status === "processing" || cleanupInFlight || uploadInFlight || renameInFlight;
    const hasJobs = getRecordingJobs(recording.id).length > 0;
    const speakerFiltersMarkup = renderRecordingSpeakerFilters(recording.id);
    const detailMarkup = summary.progressJob
      ? renderProgressMarkup(summary.progressJob)
      : `<div class="recording-detail">${escapeHtml(summary.detail)}</div>`;
    const renameMarkup = isRenaming
      ? `
        <form class="recording-rename-form" data-action="rename-recording-form" data-recording-id="${recording.id}">
          <label class="field recording-rename-field">
            <span class="field-label">Nazwa w bibliotece</span>
            <input
              class="recording-rename-input"
              type="text"
              name="original_name"
              value="${escapeHtml(recordingRenameDraft)}"
              maxlength="255"
              autocomplete="off"
              data-action="recording-rename-input"
              data-recording-id="${recording.id}"
            >
          </label>
          <div class="recording-rename-actions">
            <button class="ghost-button" type="submit" ${renameInFlight ? "disabled" : ""}>
              ${renameInFlight ? "Zapisywanie..." : "Zapisz"}
            </button>
            <button
              class="ghost-button"
              type="button"
              data-action="cancel-rename"
              data-recording-id="${recording.id}"
              ${renameInFlight ? "disabled" : ""}
            >
              Anuluj
            </button>
          </div>
        </form>
      `
      : "";

    return `
      <article class="recording-card ${isSelected ? "active" : ""}" data-action="select-recording" data-recording-id="${recording.id}">
        <div class="recording-card-top">
          <div class="recording-card-copy">
            <div class="recording-title">${escapeHtml(recording.original_name)}</div>
            <div class="recording-meta">Dodano ${formatDate(recording.created_at)}</div>
          </div>
          <span class="status-pill ${summary.tone}">${escapeHtml(summary.label)}</span>
        </div>
        ${detailMarkup}
        ${renameMarkup}
        <div class="recording-actions">
          <button
            class="ghost-button"
            type="button"
            data-action="start-rename"
            data-recording-id="${recording.id}"
            ${busy || isRenaming ? "disabled" : ""}
          >
            Zmień nazwę
          </button>
          <button
            class="ghost-button"
            type="button"
            data-action="transcribe"
            data-recording-id="${recording.id}"
            ${busy || isRenaming ? "disabled" : ""}
          >
            ${recording.status === "processing" ? "Przetwarzanie..." : hasJobs ? "Uruchom ponownie" : "Transkrybuj"}
          </button>
          <button
            class="ghost-button danger-button"
            type="button"
            data-action="delete-recording"
            data-recording-id="${recording.id}"
            data-recording-name="${escapeHtml(recording.original_name)}"
            ${busy || isRenaming ? "disabled" : ""}
          >
            Usuń
          </button>
        </div>
        ${speakerFiltersMarkup}
      </article>
    `;
  }).join("");
}

function clearPlayerSource() {
  setPlayerAudioError("");
  if (!recordingPlayer.dataset.recordingId) {
    return;
  }

  recordingPlayer.pause();
  recordingPlayer.removeAttribute("src");
  recordingPlayer.dataset.recordingId = "";
  recordingPlayer.load();
}

function setPlayerSource(recording) {
  if (!recording) {
    clearPlayerSource();
    return;
  }

  if (recordingPlayer.dataset.recordingId === recording.id) {
    return;
  }

  activeSegmentIndex = -1;
  setPlayerAudioError("");
  recordingPlayer.pause();
  recordingPlayer.src = `/api/recordings/${recording.id}/playback`;
  recordingPlayer.dataset.recordingId = recording.id;
  recordingPlayer.load();
}

function renderPlayer() {
  const selectedRecording = getSelectedRecording();
  const selectedJob = getSelectedJob();
  const activeJob = selectedRecording ? getActiveJob(selectedRecording.id) : null;
  const progressJob = activeJob || (isJobActive(selectedJob) ? selectedJob : null);

  if (!selectedRecording) {
    playerEmpty.classList.remove("hidden");
    playerView.classList.add("hidden");
    transcribeSelectedButton.disabled = true;
    transcribeSelectedButton.textContent = "Transkrybuj";
    jobProgressPanel.classList.add("hidden");
    clearPlayerSource();
    return;
  }

  playerEmpty.classList.add("hidden");
  playerView.classList.remove("hidden");
  setPlayerSource(selectedRecording);

  playerRecordingName.textContent = selectedRecording.original_name;
  playerRecordingMeta.textContent = `Dodano ${formatDate(selectedRecording.created_at)}`;
  playerRecordingStatus.textContent = progressJob
    ? `${recordingStatusLabel(selectedRecording.status)} ${getJobProgressPercent(progressJob)}%`
    : recordingStatusLabel(selectedRecording.status);
  selectedJobStatus.textContent = selectedJob ? getJobDisplayStatus(selectedJob) : "Brak joba";
  selectedJobUpdated.textContent = selectedJob ? formatDate(selectedJob.updated_at) : "Jeszcze nie uruchomiono";

  if (progressJob) {
    const percent = getJobProgressPercent(progressJob);
    jobProgressPanel.classList.remove("hidden");
    jobProgressLabel.textContent = getJobProgressMessage(progressJob);
    jobProgressPercent.textContent = `${percent}%`;
    jobProgressTrack.setAttribute("aria-valuenow", String(percent));
    jobProgressFill.style.width = `${percent}%`;
  } else {
    jobProgressPanel.classList.add("hidden");
    jobProgressLabel.textContent = "-";
    jobProgressPercent.textContent = "0%";
    jobProgressTrack.setAttribute("aria-valuenow", "0");
    jobProgressFill.style.width = "0%";
  }

  const isBusy = selectedRecording.status === "processing" || uploadInFlight || cleanupInFlight || renameInFlight;
  transcribeSelectedButton.disabled = isBusy;
  transcribeSelectedButton.dataset.recordingId = selectedRecording.id;
  transcribeSelectedButton.textContent = selectedRecording.status === "processing"
    ? "Przetwarzanie..."
    : getRecordingJobs(selectedRecording.id).length ? "Uruchom ponownie" : "Transkrybuj";

  const jobs = getRecordingJobs(selectedRecording.id);
  if (!jobs.length) {
    jobHistory.classList.add("hidden");
    jobHistory.innerHTML = "";
    return;
  }

  jobHistory.classList.remove("hidden");
  jobHistory.innerHTML = jobs.map((job) => `
    <button
      class="job-pill ${job.id === state.selectedJobId ? "active" : ""} ${job.status}"
      type="button"
      data-action="select-job"
      data-job-id="${job.id}"
    >
      <span>${escapeHtml(getJobDisplayStatus(job))}</span>
      <span>${formatShortDate(job.updated_at)}</span>
    </button>
  `).join("");
}

function canExportSelectedTranscript() {
  const selectedJob = getSelectedJob();
  return Boolean(selectedJob && selectedJob.status === "completed" && selectedJob.segments.length);
}

function renderTranscriptExportButton() {
  exportTranscriptButton.disabled = !canExportSelectedTranscript() || exportInFlight;
  exportTranscriptButton.textContent = exportInFlight ? "Pobieranie..." : "Pobierz TXT";
}

function resetClipSlotAudio(refs) {
  refs.audio.pause();
  refs.audio.removeAttribute("src");
  refs.audio.dataset.objectUrl = "";
  refs.audio.load();
}

function renderClipSlot(slotKey) {
  const refs = clipSlotRefs[slotKey];
  const slot = clipCompareSlots[slotKey];

  refs.playButton.textContent = `Odtwórz ${slotKey}`;
  refs.clearButton.disabled = !slot;
  refs.playButton.disabled = !slot;

  if (!slot) {
    refs.empty.classList.remove("hidden");
    refs.content.classList.add("hidden");
    refs.meta.textContent = "-";
    refs.text.textContent = "-";
    if (refs.audio.dataset.objectUrl) {
      resetClipSlotAudio(refs);
    }
    return;
  }

  refs.empty.classList.add("hidden");
  refs.content.classList.remove("hidden");

  const metaParts = [formatSegmentCountLabel(slot.count), formatTimecode(slot.duration)];
  if (slot.speakersLabel) {
    metaParts.push(slot.speakersLabel);
  }
  refs.meta.textContent = metaParts.join(" • ");
  refs.text.textContent = slot.excerpt || "Wybrany klip nie ma podglądu tekstu.";

  if (refs.audio.dataset.objectUrl !== slot.objectUrl) {
    refs.audio.pause();
    refs.audio.src = slot.objectUrl;
    refs.audio.dataset.objectUrl = slot.objectUrl;
    refs.audio.load();
  }
}

function renderClipTools() {
  const selectedRecording = getSelectedRecording();
  const selectedJob = getSelectedJob();
  const shouldShow = Boolean(
    selectedRecording
    && selectedJob
    && selectedJob.status === "completed"
    && selectedJob.segments.length,
  );

  if (!shouldShow) {
    clipTools.classList.add("hidden");
    clipSelectionTitle.textContent = "Zaznacz fragmenty do klipu";
    clipSelectionMeta.textContent = "Wybierz zakończony job, aby budować klipy z segmentów.";
    clipSaveAButton.disabled = true;
    clipSaveBButton.disabled = true;
    clipClearSelectionButton.disabled = true;
    clipSaveAButton.textContent = "Zapisz do A";
    clipSaveBButton.textContent = "Zapisz do B";
    return;
  }

  const summary = getClipSelectionSummary(selectedJob, selectedRecording.id);
  clipTools.classList.remove("hidden");
  clipSelectionTitle.textContent = summary.count
    ? `Zaznaczono ${formatSegmentCountLabel(summary.count)}`
    : "Zaznacz fragmenty do klipu";
  clipSelectionMeta.textContent = summary.count
    ? `${formatTimecode(summary.duration)} łącznie${summary.speakersLabel ? ` • ${summary.speakersLabel}` : ""}`
    : "Wybierz segmenty z listy poniżej, a potem zapisz je do slotu A albo B.";

  clipSaveAButton.disabled = !summary.count || clipBuildState.A;
  clipSaveBButton.disabled = !summary.count || clipBuildState.B;
  clipClearSelectionButton.disabled = !summary.count;
  clipSaveAButton.textContent = clipBuildState.A ? "Buduję A..." : "Zapisz do A";
  clipSaveBButton.textContent = clipBuildState.B ? "Buduję B..." : "Zapisz do B";
}

function renderClipComparePanel() {
  const selectedRecording = getSelectedRecording();
  const selectedJob = getSelectedJob();
  ensureClipSlotsCompatible(selectedRecording, selectedJob);

  const shouldShow = Boolean(
    selectedRecording
    && selectedJob
    && selectedJob.status === "completed"
    && selectedJob.segments.length,
  );

  if (!shouldShow) {
    stopClipSequence();
    pauseCompareAudios();
    clipComparePanel.classList.add("hidden");
    Object.keys(clipSlotRefs).forEach(renderClipSlot);
    return;
  }

  clipComparePanel.classList.remove("hidden");
  const hasA = Boolean(clipCompareSlots.A);
  const hasB = Boolean(clipCompareSlots.B);
  clipCompareMeta.textContent = hasA && hasB
    ? "Masz dwa klipy gotowe do szybkiego porównania."
    : "Zapisz dwa zestawy fragmentów, aby odsłuchać je obok siebie.";
  clipPlaySequenceButton.disabled = !hasA || !hasB || clipBuildState.A || clipBuildState.B;

  Object.keys(clipSlotRefs).forEach(renderClipSlot);
}

function clearActiveSegmentHighlight() {
  const previous = segmentsList.querySelector(".segment-card.active");
  previous?.classList.remove("active");
  activeSegmentIndex = -1;
}

function syncActiveSegment() {
  const selectedJob = getSelectedJob();
  if (!selectedJob || selectedJob.status !== "completed" || !selectedJob.segments.length) {
    clearActiveSegmentHighlight();
    return;
  }

  const nextIndex = selectedJob.segments.findIndex((segment, index) => {
    const isLast = index === selectedJob.segments.length - 1;
    return recordingPlayer.currentTime >= segment.start
      && (recordingPlayer.currentTime < segment.end || isLast);
  });

  if (nextIndex === activeSegmentIndex) {
    return;
  }

  const previous = segmentsList.querySelector(`.segment-card[data-segment-index="${activeSegmentIndex}"]`);
  previous?.classList.remove("active");

  const next = segmentsList.querySelector(`.segment-card[data-segment-index="${nextIndex}"]`);
  next?.classList.add("active");

  activeSegmentIndex = nextIndex;
}

function showTranscriptEmpty(message) {
  transcriptSummaryMeta.textContent = "Kliknij timestamp, aby odtwarzacz przeskoczył do danego miejsca.";
  transcriptEmpty.textContent = message;
  transcriptEmpty.classList.remove("hidden");
  transcriptView.classList.add("hidden");
  segmentsList.innerHTML = "";
  segmentsList.dataset.renderKey = "";
  clearActiveSegmentHighlight();
}

function renderTranscript() {
  const selectedRecording = getSelectedRecording();
  const selectedJob = getSelectedJob();

  if (!selectedRecording) {
    showTranscriptEmpty("Dodaj nagranie albo wybierz je z listy. Tutaj pojawi się podział na mówców.");
    return;
  }

  if (!selectedJob) {
    showTranscriptEmpty("To nagranie nie ma jeszcze joba. Uruchom transkrypcję z poziomu odtwarzacza.");
    return;
  }

  if (selectedJob.status === "queued") {
    showTranscriptEmpty(`${getJobDisplayStatus(selectedJob)}. ${getJobProgressMessage(selectedJob)}`);
    return;
  }

  if (selectedJob.status === "running") {
    showTranscriptEmpty(`${getJobDisplayStatus(selectedJob)}. ${getJobProgressMessage(selectedJob)} Odświeżenie nastąpi automatycznie.`);
    return;
  }

  if (selectedJob.status === "failed") {
    showTranscriptEmpty(selectedJob.error
      ? `Transkrypcja zakończyła się błędem: ${selectedJob.error}`
      : "Transkrypcja zakończyła się błędem.");
    return;
  }

  transcriptEmpty.classList.add("hidden");
  transcriptView.classList.remove("hidden");

  const visibleSegments = getVisibleSegments(selectedJob, selectedRecording.id);
  const selectedSegmentIndexes = new Set(getClipSelectionIndexes(selectedJob));
  const transcriptRenderKey = [
    selectedJob.id,
    selectedJob.updated_at,
    selectedJob.status,
    getSpeakerPrefsSignature(selectedRecording.id),
    getClipSelectionSignature(selectedJob),
  ].join(":");

  transcriptSummaryMeta.textContent = selectedJob.segments.length
    ? `Widoczne ${visibleSegments.length} z ${selectedJob.segments.length} segmentów. Kliknij timestamp, aby przejść do danego miejsca.`
    : "Wynik nie zawiera segmentów mówców.";

  if (segmentsList.dataset.renderKey !== transcriptRenderKey) {
    if (!selectedJob.segments.length) {
      segmentsList.innerHTML = '<div class="empty-state compact-empty">Brak segmentów do wyświetlenia.</div>';
    } else if (!visibleSegments.length) {
      segmentsList.innerHTML = '<div class="empty-state compact-empty">Wszyscy speakerzy są odfiltrowani. Zaznacz co najmniej jednego, aby zobaczyć wypowiedzi.</div>';
    } else {
      segmentsList.innerHTML = visibleSegments.map(({ segment, index, displayName }) => {
        const isSelected = selectedSegmentIndexes.has(index);
        return `
        <section class="segment-card ${isSelected ? "is-selected" : ""}" data-segment-index="${index}">
          <div class="segment-meta">
            <div class="segment-speaker-group">
              <button
                type="button"
                class="speaker-name-button"
                data-action="rename-speaker"
                data-speaker="${escapeHtml(segment.speaker)}"
              >
                ${escapeHtml(displayName)}
              </button>
              ${displayName !== segment.speaker
                ? `<span class="segment-speaker-origin">${escapeHtml(segment.speaker)}</span>`
                : ""}
            </div>
            <div class="segment-actions">
              <button
                type="button"
                class="ghost-button segment-select-button ${isSelected ? "is-selected" : ""}"
                data-action="toggle-segment-selection"
                data-segment-index="${index}"
              >
                ${isSelected ? "Wybrane" : "Zaznacz"}
              </button>
              <button
                type="button"
                class="timestamp-button"
                data-action="seek-segment"
                data-seconds="${segment.start}"
              >
                ${formatTimecode(segment.start)}
              </button>
            </div>
          </div>
          <p class="segment-text">${escapeHtml(segment.text)}</p>
          <div class="segment-range">${formatTimecode(segment.start)} - ${formatTimecode(segment.end)}</div>
        </section>
      `;
      }).join("");
    }

    segmentsList.dataset.renderKey = transcriptRenderKey;
    activeSegmentIndex = -1;
  }

  syncActiveSegment();
}

function renderAll() {
  syncSelection();
  renderStatus();
  renderSettingsForm();
  renderRecordings();
  renderPlayer();
  renderTranscriptExportButton();
  renderClipTools();
  renderTranscript();
  renderClipComparePanel();
}

async function refreshState({ force = false } = {}) {
  if (refreshInFlight || (!force && (uploadInFlight || cleanupInFlight))) {
    return;
  }

  refreshInFlight = true;
  try {
    const [health, settings, recordings, jobs] = await Promise.all([
      api("/api/health"),
      api("/api/settings"),
      api("/api/recordings"),
      api("/api/jobs"),
    ]);

    state.health = health;
    state.settings = settings;
    state.recordings = recordings;
    state.jobs = jobs;
    renderAll();
  } finally {
    refreshInFlight = false;
  }
}

function getUploadLabel(fileName, index, total) {
  if (total > 1) {
    return `plik ${index} z ${total}: ${fileName}`;
  }
  return `plik ${fileName}`;
}

function importRecording(file, { index = 1, total = 1 } = {}) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    const uploadLabel = getUploadLabel(file.name, index, total);
    request.open("POST", `/api/recordings/import/raw?filename=${encodeURIComponent(file.name)}`, true);
    request.responseType = "json";
    request.timeout = 10 * 60 * 1000;
    request.setRequestHeader("Content-Type", file.type || "application/octet-stream");

    request.upload.onprogress = (event) => {
      if (!event.lengthComputable) {
        setUploadStatus(`Wysyłanie ${uploadLabel}...`);
        return;
      }

      const percent = Math.max(1, Math.min(100, Math.round((event.loaded / event.total) * 100)));
      setUploadStatus(`Wysyłanie ${uploadLabel}: ${percent}%`);
    };

    request.onerror = () => {
      reject(new Error("Przeglądarka nie mogła wysłać pliku do lokalnego backendu."));
    };

    request.onabort = () => {
      reject(new Error("Wysyłanie pliku zostało przerwane."));
    };

    request.ontimeout = () => {
      reject(new Error("Upload przekroczył limit czasu."));
    };

    request.onload = () => {
      const payload = readXhrPayload(request);
      if (request.status >= 200 && request.status < 300) {
        resolve(payload);
        return;
      }

      if (payload && typeof payload === "object") {
        reject(new Error(payload.detail || payload.message || `Request failed: ${request.status}`));
        return;
      }

      reject(new Error(request.responseText || `Request failed: ${request.status}`));
    };

    setUploadStatus(`Przygotowanie uploadu: ${uploadLabel}`);
    request.send(file);
  });
}

async function deleteRecording(recordingId) {
  return api(`/api/recordings/${recordingId}`, {
    method: "DELETE",
  });
}

async function clearAllRecordings() {
  return api("/api/recordings/clear", {
    method: "POST",
  });
}

async function updateRecordingName(recordingId, originalName) {
  return api(`/api/recordings/${recordingId}`, {
    method: "PATCH",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      original_name: originalName,
    }),
  });
}

function serializeSettingsForm() {
  return {
    whisper_model: settingsWhisperModelSelect.value.trim(),
    whisper_device: settingsWhisperDeviceSelect.value.trim().toLowerCase(),
    diarization_model: settingsDiarizationModelInput.value.trim(),
    diarization_device: settingsDiarizationDeviceSelect.value.trim().toLowerCase(),
  };
}

async function updateSettings(payload) {
  return api("/api/settings", {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

async function startTranscription(recordingId) {
  const job = await api(`/api/jobs/transcribe/${recordingId}`, {
    method: "POST",
  });
  state.selectedRecordingId = recordingId;
  state.selectedJobId = job.id;
  return job;
}

function readResponseFilename(contentDisposition) {
  if (!contentDisposition) {
    return null;
  }

  const encodedMatch = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i);
  if (encodedMatch) {
    try {
      return decodeURIComponent(encodedMatch[1]);
    } catch (_) {}
  }

  const plainMatch = contentDisposition.match(/filename="?([^"]+)"?/i);
  return plainMatch?.[1] || null;
}

async function exportTranscript(jobId, recordingId) {
  let response;
  try {
    response = await fetch(`/api/jobs/${jobId}/export/txt`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        speaker_names: getSpeakerNameOverrides(recordingId),
      }),
    });
  } catch (_) {
    throw new Error("Backend niedostępny albo połączenie zostało przerwane.");
  }

  if (!response.ok) {
    const payload = await response.text();
    let message = payload || `Request failed: ${response.status}`;

    try {
      const parsed = JSON.parse(payload);
      message = parsed.detail || parsed.message || message;
    } catch (_) {
      message = payload || message;
    }

    throw new Error(message);
  }

  return {
    blob: await response.blob(),
    filename: readResponseFilename(response.headers.get("Content-Disposition")) || "transcript_diarized.txt",
  };
}

async function buildClipPreview(recordingId, ranges) {
  let response;
  try {
    response = await fetch(`/api/recordings/${recordingId}/clips/preview`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ranges,
        padding_ms: 180,
      }),
    });
  } catch (_) {
    throw new Error("Backend niedostępny albo połączenie zostało przerwane.");
  }

  if (!response.ok) {
    const payload = await response.text();
    let message = payload || `Request failed: ${response.status}`;

    try {
      const parsed = JSON.parse(payload);
      message = parsed.detail || parsed.message || message;
    } catch (_) {
      message = payload || message;
    }

    throw new Error(message);
  }

  return {
    blob: await response.blob(),
    filename: readResponseFilename(response.headers.get("Content-Disposition")) || "clip.wav",
  };
}

function triggerFileDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

async function saveSelectionToClipSlot(slotKey) {
  const selectedRecording = getSelectedRecording();
  const selectedJob = getSelectedJob();
  if (
    !selectedRecording
    || !selectedJob
    || selectedJob.status !== "completed"
    || clipBuildState[slotKey]
  ) {
    return;
  }

  const summary = getClipSelectionSummary(selectedJob, selectedRecording.id);
  if (!summary.count) {
    window.alert("Zaznacz co najmniej jeden segment, aby zbudować klip.");
    return;
  }

  clipBuildState[slotKey] = true;
  renderClipTools();
  renderClipComparePanel();

  try {
    const { blob, filename } = await buildClipPreview(selectedRecording.id, summary.ranges);
    setClipCompareSlot(slotKey, {
      recordingId: selectedRecording.id,
      jobId: selectedJob.id,
      objectUrl: URL.createObjectURL(blob),
      filename,
      count: summary.count,
      duration: summary.duration,
      speakersLabel: summary.speakersLabel,
      excerpt: summary.excerpt,
    });
    clearClipSelection(selectedJob.id);
  } catch (error) {
    window.alert(`Nie udało się zbudować klipu ${slotKey}: ${error.message}`);
  } finally {
    clipBuildState[slotKey] = false;
    renderAll();
  }
}

function playClipSlot(slotKey) {
  const slot = clipCompareSlots[slotKey];
  if (!slot) {
    return;
  }

  stopClipSequence();
  recordingPlayer.pause();
  pauseCompareAudios({ except: slotKey });
  const audio = clipSlotRefs[slotKey].audio;
  audio.currentTime = 0;
  audio.play().catch(() => {});
}

async function playClipSequence() {
  if (!clipCompareSlots.A || !clipCompareSlots.B) {
    return;
  }

  stopClipSequence();
  clipSequenceMode = "running";
  recordingPlayer.pause();
  pauseCompareAudios();

  const audioA = clipSlotRefs.A.audio;
  const audioB = clipSlotRefs.B.audio;
  audioA.currentTime = 0;
  audioB.currentTime = 0;

  try {
    await audioA.play();
  } catch (_) {
    stopClipSequence();
  }
}

function openSettingsModal() {
  modalReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  settingsModal.classList.remove("hidden");
  settingsModal.setAttribute("aria-hidden", "false");
  document.body.classList.add("modal-open");
  closeSettingsButton.focus();
}

function closeSettingsModal() {
  settingsModal.classList.add("hidden");
  settingsModal.setAttribute("aria-hidden", "true");
  document.body.classList.remove("modal-open");

  if (modalReturnFocus instanceof HTMLElement) {
    modalReturnFocus.focus();
  }
  modalReturnFocus = null;
}

function markSettingsDirty() {
  if (!state.settings) {
    return;
  }

  settingsFormDirty = true;
  renderSettingsForm();
  if (!settingsSaveInFlight) {
    setSettingsStatus("Masz niezapisane zmiany.");
  }
}

function isShortcutBlockedTarget(target) {
  if (!(target instanceof HTMLElement)) {
    return false;
  }

  if (target === recordingPlayer) {
    return false;
  }

  return target.isContentEditable || Boolean(target.closest("input, textarea, select, button, a, summary"));
}

function setPlaybackTime(seconds, { autoplay = true } = {}) {
  if (!recordingPlayer.dataset.recordingId) {
    return;
  }

  const applySeek = () => {
    const duration = Number.isFinite(recordingPlayer.duration) ? recordingPlayer.duration : null;
    const targetTime = duration ? Math.min(seconds, Math.max(0, duration - 0.05)) : Math.max(0, seconds);
    recordingPlayer.currentTime = targetTime;
    syncActiveSegment();
    if (autoplay) {
      recordingPlayer.play().catch(() => {});
    }
  };

  if (recordingPlayer.readyState >= 1) {
    applySeek();
    return;
  }

  const onLoadedMetadata = () => {
    recordingPlayer.removeEventListener("loadedmetadata", onLoadedMetadata);
    applySeek();
  };

  recordingPlayer.addEventListener("loadedmetadata", onLoadedMetadata);
  recordingPlayer.load();
}

function seekTo(seconds, options = {}) {
  setPlaybackTime(seconds, options);
}

function seekBy(deltaSeconds) {
  if (!recordingPlayer.dataset.recordingId) {
    return;
  }

  setPlaybackTime(recordingPlayer.currentTime + deltaSeconds, {
    autoplay: !recordingPlayer.paused,
  });
}

function togglePlayback() {
  if (!recordingPlayer.dataset.recordingId) {
    return;
  }

  if (recordingPlayer.paused || recordingPlayer.ended) {
    recordingPlayer.play().catch(() => {});
    return;
  }

  recordingPlayer.pause();
}

recordingPlayer.addEventListener("error", () => {
  const selectedRecording = getSelectedRecording();
  const recordingName = selectedRecording?.original_name || "wybranego pliku";
  setPlayerAudioError(
    `Nie udało się odtworzyć ${recordingName}. Sprawdź, czy backend ma dostęp do ffmpeg i czy plik audio nie jest uszkodzony.`,
  );
});

themeButtons.forEach((button) => {
  button.addEventListener("click", () => {
    saveTheme(button.dataset.themeOption);
  });
});

openSettingsButton.addEventListener("click", openSettingsModal);
closeSettingsButton.addEventListener("click", closeSettingsModal);
settingsModal.addEventListener("click", (event) => {
  const target = event.target.closest('[data-action="close-settings"]');
  if (!target) {
    return;
  }
  closeSettingsModal();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !settingsModal.classList.contains("hidden")) {
    closeSettingsModal();
    return;
  }

  if (
    event.defaultPrevented
    || event.altKey
    || event.ctrlKey
    || event.metaKey
    || !settingsModal.classList.contains("hidden")
    || !recordingPlayer.dataset.recordingId
    || isShortcutBlockedTarget(event.target)
  ) {
    return;
  }

  if (event.code === "Space") {
    if (event.repeat) {
      return;
    }

    event.preventDefault();
    togglePlayback();
    return;
  }

  if (event.key === "ArrowLeft") {
    event.preventDefault();
    seekBy(-10);
    return;
  }

  if (event.key === "ArrowRight") {
    event.preventDefault();
    seekBy(10);
  }
});

settingsForm.addEventListener("input", markSettingsDirty);
settingsForm.addEventListener("change", markSettingsDirty);

recordingPlayer.addEventListener("timeupdate", syncActiveSegment);
recordingPlayer.addEventListener("seeked", syncActiveSegment);
recordingPlayer.addEventListener("canplay", () => setPlayerAudioError(""));
recordingPlayer.addEventListener("loadedmetadata", syncActiveSegment);
recordingPlayer.addEventListener("play", () => {
  stopClipSequence();
  pauseCompareAudios();
});

Object.entries(clipSlotRefs).forEach(([slotKey, refs]) => {
  refs.audio.addEventListener("play", () => {
    recordingPlayer.pause();
    pauseCompareAudios({ except: slotKey });
  });

  refs.audio.addEventListener("ended", () => {
    if (clipSequenceMode !== "running") {
      return;
    }

    if (slotKey === "A" && clipCompareSlots.B) {
      const audioB = clipSlotRefs.B.audio;
      audioB.currentTime = 0;
      audioB.play().catch(() => {
        stopClipSequence();
      });
      return;
    }

    stopClipSequence();
  });
});

applyTheme(getStoredTheme());

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const files = Array.from(recordingFileInput.files || []);
  if (!files.length || uploadInFlight) {
    return;
  }

  uploadInFlight = true;
  resetRecordingRename();
  uploadSubmitButton.disabled = true;
  renderAll();

  try {
    let successCount = 0;
    let lastRecording = null;
    const failures = [];

    for (const [index, file] of files.entries()) {
      try {
        lastRecording = await importRecording(file, {
          index: index + 1,
          total: files.length,
        });
        successCount += 1;
      } catch (error) {
        failures.push(`${file.name}: ${error.message}`);
      }
    }

    recordingFileInput.value = "";
    if (lastRecording) {
      state.selectedRecordingId = lastRecording.id;
      state.selectedJobId = null;
    }
    await refreshState({ force: true });

    if (!failures.length) {
      setUploadStatus(
        successCount === 1
          ? `Zaimportowano plik: ${files[0].name}`
          : `Zaimportowano ${successCount} plików.`,
        "success",
      );
      return;
    }

    if (successCount > 0) {
      setUploadStatus(`Zaimportowano ${successCount} z ${files.length} plików.`, "error");
      window.alert(`Nie wszystkie pliki udało się zaimportować:\n- ${failures.join("\n- ")}`);
      return;
    }

    const message = failures[0] || "Nieznany błąd uploadu.";
    setUploadStatus(`Błąd uploadu: ${message}`, "error");
    window.alert(`Nie udało się zaimportować plików:\n- ${failures.join("\n- ")}`);
  } catch (error) {
    setUploadStatus(`Błąd uploadu: ${error.message}`, "error");
    window.alert(`Nie udało się zaimportować plików: ${error.message}`);
  } finally {
    uploadInFlight = false;
    uploadSubmitButton.disabled = false;
    renderAll();
  }
});

async function handleTranscription(recordingId) {
  if (!recordingId) {
    return;
  }

  try {
    await startTranscription(recordingId);
    await refreshState({ force: true });
  } catch (error) {
    window.alert(`Nie udało się wystartować transkrypcji: ${error.message}`);
  } finally {
    renderAll();
  }
}

recordingsList.addEventListener("click", async (event) => {
  const renameSpeakerTarget = event.target.closest('[data-action="rename-speaker"]');
  if (renameSpeakerTarget) {
    renameSpeaker(state.selectedRecordingId, renameSpeakerTarget.dataset.speaker);
    return;
  }

  const startRenameTarget = event.target.closest('[data-action="start-rename"]');
  if (startRenameTarget) {
    startRecordingRename(startRenameTarget.dataset.recordingId);
    return;
  }

  const cancelRenameTarget = event.target.closest('[data-action="cancel-rename"]');
  if (cancelRenameTarget) {
    cancelRecordingRename();
    return;
  }

  const deleteTarget = event.target.closest('[data-action="delete-recording"]');
  if (deleteTarget) {
    const { recordingId, recordingName } = deleteTarget.dataset;
    if (!window.confirm(`Usunąć nagranie "${recordingName}" i powiązane joby?`)) {
      return;
    }

    cleanupInFlight = true;
    setUploadStatus(`Usuwanie pliku: ${recordingName}`);
    try {
      await deleteRecording(recordingId);
      if (state.selectedRecordingId === recordingId) {
        state.selectedRecordingId = null;
        state.selectedJobId = null;
      }
      await refreshState({ force: true });
      setUploadStatus(`Usunięto plik: ${recordingName}`, "success");
    } catch (error) {
      setUploadStatus(`Błąd usuwania: ${error.message}`, "error");
      window.alert(`Nie udało się usunąć pliku: ${error.message}`);
    } finally {
      cleanupInFlight = false;
      renderAll();
    }
    return;
  }

  const transcribeTarget = event.target.closest('[data-action="transcribe"]');
  if (transcribeTarget) {
    transcribeTarget.disabled = true;
    await handleTranscription(transcribeTarget.dataset.recordingId);
    return;
  }

  if (event.target.closest(".recording-rename-form")) {
    return;
  }

  if (event.target.closest('[data-action="speaker-filters-panel"]')) {
    return;
  }

  const selectTarget = event.target.closest('[data-action="select-recording"]');
  if (!selectTarget) {
    return;
  }

  if (renamingRecordingId && renamingRecordingId !== selectTarget.dataset.recordingId) {
    resetRecordingRename();
  }
  state.selectedRecordingId = selectTarget.dataset.recordingId;
  state.selectedJobId = null;
  renderAll();
});

recordingsList.addEventListener("input", (event) => {
  const target = event.target.closest('[data-action="recording-rename-input"]');
  if (!target || target.dataset.recordingId !== renamingRecordingId) {
    return;
  }

  recordingRenameDraft = target.value;
});

recordingsList.addEventListener("change", (event) => {
  const target = event.target.closest('[data-action="toggle-speaker"]');
  if (!target) {
    return;
  }

  setSpeakerHidden(state.selectedRecordingId, target.dataset.speaker, !target.checked);
  renderAll();
});

recordingsList.addEventListener("toggle", (event) => {
  const target = event.target.closest('[data-action="speaker-filters-panel"]');
  if (!target) {
    return;
  }

  const recordingCard = target.closest('[data-recording-id]');
  if (!recordingCard?.dataset.recordingId) {
    return;
  }

  speakerFilterPanelState[recordingCard.dataset.recordingId] = target.open;
}, true);

recordingsList.addEventListener("submit", async (event) => {
  const form = event.target.closest('[data-action="rename-recording-form"]');
  if (!form) {
    return;
  }

  event.preventDefault();
  if (renameInFlight) {
    return;
  }

  const { recordingId } = form.dataset;
  const currentRecording = getRecordingById(recordingId);
  if (!currentRecording) {
    resetRecordingRename();
    renderAll();
    return;
  }

  const nextName = String(recordingRenameDraft || "").trim();
  if (!nextName) {
    setUploadStatus("Nazwa nagrania nie może być pusta.", "error");
    focusRecordingRenameInput(recordingId);
    return;
  }

  renameInFlight = true;
  renderAll();
  setUploadStatus(`Zapisywanie nazwy: ${currentRecording.original_name}`);
  let shouldRestoreRenameFocus = false;

  try {
    const updated = await updateRecordingName(recordingId, nextName);
    state.recordings = state.recordings.map((recording) => (recording.id === updated.id ? updated : recording));
    resetRecordingRename();
    await refreshState({ force: true });
    setUploadStatus(`Zmieniono nazwę na: ${updated.original_name}`, "success");
  } catch (error) {
    setUploadStatus(`Błąd zmiany nazwy: ${error.message}`, "error");
    window.alert(`Nie udało się zmienić nazwy nagrania: ${error.message}`);
    shouldRestoreRenameFocus = true;
  } finally {
    renameInFlight = false;
    renderAll();
    if (shouldRestoreRenameFocus) {
      focusRecordingRenameInput(recordingId);
    }
  }
});

transcribeSelectedButton.addEventListener("click", async () => {
  if (transcribeSelectedButton.disabled) {
    return;
  }

  transcribeSelectedButton.disabled = true;
  await handleTranscription(transcribeSelectedButton.dataset.recordingId);
});

exportTranscriptButton.addEventListener("click", async () => {
  const selectedRecording = getSelectedRecording();
  const selectedJob = getSelectedJob();
  if (!selectedRecording || !selectedJob || exportTranscriptButton.disabled) {
    return;
  }

  exportInFlight = true;
  renderTranscriptExportButton();
  setUploadStatus(`Przygotowanie eksportu TXT: ${selectedRecording.original_name}`);

  try {
    const { blob, filename } = await exportTranscript(selectedJob.id, selectedRecording.id);
    triggerFileDownload(blob, filename);
    setUploadStatus(`Pobrano plik TXT: ${filename}`, "success");
  } catch (error) {
    setUploadStatus(`Błąd eksportu TXT: ${error.message}`, "error");
    window.alert(`Nie udało się pobrać pliku TXT: ${error.message}`);
  } finally {
    exportInFlight = false;
    renderTranscriptExportButton();
  }
});

clipSaveAButton.addEventListener("click", async () => {
  await saveSelectionToClipSlot("A");
});

clipSaveBButton.addEventListener("click", async () => {
  await saveSelectionToClipSlot("B");
});

clipClearSelectionButton.addEventListener("click", () => {
  const selectedJob = getSelectedJob();
  if (!selectedJob) {
    return;
  }

  clearClipSelection(selectedJob.id);
  renderAll();
});

clipPlaySequenceButton.addEventListener("click", async () => {
  await playClipSequence();
});

clipSlotRefs.A.playButton.addEventListener("click", () => {
  playClipSlot("A");
});

clipSlotRefs.B.playButton.addEventListener("click", () => {
  playClipSlot("B");
});

clipSlotRefs.A.clearButton.addEventListener("click", () => {
  stopClipSequence();
  clearClipCompareSlot("A");
  renderClipComparePanel();
});

clipSlotRefs.B.clearButton.addEventListener("click", () => {
  stopClipSequence();
  clearClipCompareSlot("B");
  renderClipComparePanel();
});

clearRecordingsButton.addEventListener("click", async () => {
  if (!state.recordings.length) {
    return;
  }

  if (!window.confirm("Usunąć wszystkie zaimportowane pliki i powiązane joby?")) {
    return;
  }

  cleanupInFlight = true;
  clearRecordingsButton.disabled = true;
  setUploadStatus("Czyszczenie wszystkich plików...");
  try {
    const result = await clearAllRecordings();
    state.selectedRecordingId = null;
    state.selectedJobId = null;
    await refreshState({ force: true });
    setUploadStatus(
      `Wyczyszczono ${result.files_deleted} plików i ${result.jobs_deleted} jobów.`,
      "success",
    );
  } catch (error) {
    setUploadStatus(`Błąd czyszczenia: ${error.message}`, "error");
    window.alert(`Nie udało się wyczyścić plików: ${error.message}`);
  } finally {
    cleanupInFlight = false;
    renderAll();
  }
});

settingsForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.settings || settingsSaveInFlight) {
    return;
  }

  const payload = serializeSettingsForm();
  if (!payload.whisper_model || !payload.diarization_model) {
    setSettingsStatus("Model Whisper i model diarizacji są wymagane.", "error");
    return;
  }

  settingsSaveInFlight = true;
  renderSettingsForm();
  setSettingsStatus("Zapisywanie konfiguracji...");

  try {
    state.settings = await updateSettings(payload);
    settingsFormDirty = false;
    renderStatus();
    renderSettingsForm({ force: true });
    setSettingsStatus("Zapisano konfigurację.", "success");
    await refreshState({ force: true });
  } catch (error) {
    setSettingsStatus(`Błąd zapisu: ${error.message}`, "error");
    window.alert(`Nie udało się zapisać konfiguracji: ${error.message}`);
  } finally {
    settingsSaveInFlight = false;
    renderSettingsForm();
  }
});

jobHistory.addEventListener("click", (event) => {
  const target = event.target.closest('[data-action="select-job"]');
  if (!target) {
    return;
  }

  const job = state.jobs.find((item) => item.id === target.dataset.jobId);
  if (!job) {
    return;
  }

  state.selectedRecordingId = job.recording_id;
  state.selectedJobId = job.id;
  renderAll();
});

segmentsList.addEventListener("click", (event) => {
  const selectionTarget = event.target.closest('[data-action="toggle-segment-selection"]');
  if (selectionTarget) {
    const selectedJob = getSelectedJob();
    if (!selectedJob) {
      return;
    }

    toggleClipSelection(selectedJob, Number(selectionTarget.dataset.segmentIndex));
    renderAll();
    return;
  }

  const renameTarget = event.target.closest('[data-action="rename-speaker"]');
  if (renameTarget) {
    renameSpeaker(state.selectedRecordingId, renameTarget.dataset.speaker);
    return;
  }

  const target = event.target.closest('[data-action="seek-segment"]');
  if (!target) {
    return;
  }

  seekTo(Number(target.dataset.seconds));
});

refreshState().catch((error) => {
  refreshInFlight = false;
  state.health = null;
  renderStatus();
  setUploadStatus(`Backend offline: ${error.message}`, "error");
});

window.addEventListener("beforeunload", () => {
  stopClipSequence();
  Object.keys(clipCompareSlots).forEach(clearClipCompareSlot);
});

window.setInterval(() => {
  if (uploadInFlight || cleanupInFlight || renameInFlight || renamingRecordingId) {
    return;
  }

  refreshState().catch((error) => {
    refreshInFlight = false;
    state.health = null;
    renderStatus();
    setUploadStatus(`Backend offline: ${error.message}`, "error");
  });
}, 2500);
