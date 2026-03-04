/**
 * DeployPulse - Frontend JavaScript
 * Handles form submission and real-time progress streaming
 */

// ============================================================================
// DOM Elements
// ============================================================================

const formSection = document.getElementById('form-section');
const progressSection = document.getElementById('progress-section');
const resultsSection = document.getElementById('results-section');

const executionForm = document.getElementById('execution-form');
const executeBtn = document.getElementById('execute-btn');
const backBtn = document.getElementById('back-btn');

const logsContainer = document.getElementById('logs-container');
const progressError = document.getElementById('progress-error');

// ============================================================================
// State Management
// ============================================================================

let eventSource = null;

// ============================================================================
// Utility Functions
// ============================================================================

/**
 * Hide all sections and show the one specified
 */
function showSection(section) {
  formSection.classList.add('form-hidden');
  formSection.classList.remove('form-visible');

  progressSection.classList.add('progress-hidden');
  progressSection.classList.remove('progress-visible');

  resultsSection.classList.add('results-hidden');
  resultsSection.classList.remove('results-visible');

  if (section === 'form') {
    formSection.classList.remove('form-hidden');
    formSection.classList.add('form-visible');
  } else if (section === 'progress') {
    progressSection.classList.remove('progress-hidden');
    progressSection.classList.add('progress-visible');
  } else if (section === 'results') {
    resultsSection.classList.remove('results-hidden');
    resultsSection.classList.add('results-visible');
  }
}

/**
 * Add a log entry with the specified type and message
 */
function addLog(message, type = 'info') {
  const entry = document.createElement('div');
  entry.className = `log-entry log-${type}`;
  entry.textContent = message;
  logsContainer.appendChild(entry);

  // Auto-scroll to bottom
  logsContainer.scrollTop = logsContainer.scrollHeight;
}

/**
 * Clear all logs
 */
function clearLogs() {
  logsContainer.innerHTML = '';
  progressError.style.display = 'none';
  progressError.textContent = '';
}

/**
 * Get form values
 */
function getFormValues() {
  const environment = document.querySelector(
    'input[name="environment"]:checked',
  )?.value;
  const event = document.querySelector('input[name="event"]:checked')?.value;
  const ticket_id = document.getElementById('ticket-id').value.trim();

  return { environment, event, ticket_id };
}

/**
 * Validate form
 */
function validateForm() {
  const { environment, event, ticket_id } = getFormValues();

  if (!environment) {
    alert('Please select an environment');
    return false;
  }

  if (!event) {
    alert('Please select an event');
    return false;
  }

  if (!ticket_id) {
    alert('Please enter a ticket number');
    return false;
  }

  if (!/^[A-Za-z0-9]+$/.test(ticket_id)) {
    alert('Ticket number should only contain letters and numbers');
    return false;
  }

  return true;
}

/**
 * Format environment value for display
 */
function formatEnvironment(env) {
  const map = {
    dev: 'DEV',
    qa: 'QA',
    stage: 'STG',
    prod: 'PROD',
  };
  return map[env] || env;
}

/**
 * Format event value for display
 */
function formatEvent(evt) {
  const map = {
    pre: 'Pre-Deployment',
    post: 'Post-Deployment',
  };
  return map[evt] || evt;
}

// ============================================================================
// Form Submission Handler
// ============================================================================

executionForm.addEventListener('submit', async (e) => {
  e.preventDefault();

  // Validate form
  if (!validateForm()) {
    return;
  }

  const { environment, event, ticket_id } = getFormValues();

  // Update progress section
  document.getElementById('progress-ticket-id').textContent = ticket_id;
  document.getElementById('progress-env').textContent =
    formatEnvironment(environment);
  document.getElementById('progress-event').textContent = formatEvent(event);

  // Clear logs and show progress
  clearLogs();
  showSection('progress');
  executeBtn.disabled = true;

  // Start streaming
  startExecution(environment, event, ticket_id);
});

// ============================================================================
// Server-Sent Events (SSE) Streaming
// ============================================================================

function startExecution(environment, event, ticket_id) {
  // Close any existing connection
  if (eventSource) {
    eventSource.close();
  }

  // Create request payload
  const payload = {
    environment,
    event,
    ticket_id,
  };

  // Create EventSource for streaming
  eventSource = new EventSource(
    `/api/execute-stream?${new URLSearchParams(payload)}`,
  );

  // Handle incoming messages
  eventSource.addEventListener('message', (event) => {
    try {
      const data = JSON.parse(event.data);
      handleStreamMessage(data);
    } catch (error) {
      console.error('Error parsing stream message:', error);
      addLog('Error parsing response', 'error');
    }
  });

  // Handle errors
  eventSource.addEventListener('error', (error) => {
    console.error('Stream error:', error);
    eventSource.close();

    if (eventSource.readyState === EventSource.CLOSED) {
      // Connection closed (may be intentional)
      if (logsContainer.children.length === 0) {
        showError('Connection lost. Please try again.');
      }
    } else {
      showError('Connection error. Please check your internet connection.');
    }

    executeBtn.disabled = false;
  });
}

/**
 * Handle incoming stream messages
 */
function handleStreamMessage(data) {
  const { status, message, ...rest } = data;

  if (status === 'info') {
    addLog(message, 'info');
  } else if (status === 'success') {
    addLog(message, 'success');
  } else if (status === 'warning') {
    addLog(message, 'warning');
    showError(message);
  } else if (status === 'error') {
    addLog(message, 'error');
    showError(message);
    eventSource.close();
    executeBtn.disabled = false;
  } else if (status === 'complete') {
    handleExecutionComplete(rest);
  }
}

/**
 * Show error message
 */
function showError(message) {
  progressError.style.display = 'block';
  progressError.textContent = '❌ ' + message;
}

/**
 * Handle execution completion
 */
function handleExecutionComplete(data) {
  eventSource.close();

  const { ticket_id, environment, event, snapshots, reports } = data;

  // Build results HTML
  let resultsHTML = '';

  // Snapshots
  if (snapshots && snapshots.length > 0) {
    resultsHTML += '<h3>📊 Snapshots</h3>';
    resultsHTML += "<ul class='file-list'>";
    snapshots.forEach((file) => {
      const fileName = file.split('/').pop();
      resultsHTML += `<li class="file-item"><a href="/api/download-file/${file}" class="file-link" download>${fileName}</a></li>`;
    });
    resultsHTML += '</ul>';
  }

  // Reports
  if (reports && reports.length > 0) {
    resultsHTML += '<h3>📄 Reports</h3>';
    resultsHTML += "<ul class='file-list'>";
    reports.forEach((file) => {
      const fileName = file.split('/').pop();
      resultsHTML += `<li class="file-item"><a href="/api/download-file/${file}" class="file-link" download>${fileName}</a></li>`;
    });
    resultsHTML += '</ul>';
  }

  // Populate results
  document.getElementById('results-message').textContent =
    '✓ Execution completed successfully!';

  const filesContainer = document.getElementById('results-files');
  if (resultsHTML) {
    filesContainer.innerHTML = resultsHTML;
  } else {
    filesContainer.innerHTML =
      '<p>No files generated. Check logs for details.</p>';
  }

  // Show results section
  showSection('results');
  executeBtn.disabled = false;
}

// ============================================================================
// Back Button Handler
// ============================================================================

backBtn.addEventListener('click', () => {
  // Close event source if still open
  if (eventSource) {
    eventSource.close();
  }

  // Reset form
  executionForm.reset();

  // Show form section
  showSection('form');
  executeBtn.disabled = false;
});

// ============================================================================
// Initialization
// ============================================================================

document.addEventListener('DOMContentLoaded', () => {
  // Form is shown by default
  showSection('form');

  // Add page unload handler to close stream if needed
  window.addEventListener('beforeunload', () => {
    if (eventSource) {
      eventSource.close();
    }
  });
});
