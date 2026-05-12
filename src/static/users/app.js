const jsonHeaders = { 'Content-Type': 'application/json' };
const state = {
  challenges: [],
  activeCategory: 'all',
  currentChallenge: null,
  user: null,
  team: null,
  solves: [],
  teamSolves: [],
  running: new Map(JSON.parse(localStorage.getItem('kubebitRunning') || '[]')),
  solved: new Set(),
  teamSolved: new Set(),
  teamSolvedBy: new Map()
};

const grid = document.querySelector('#challengeGrid');
const filters = document.querySelector('#filters');
const search = document.querySelector('#search');
const modal = document.querySelector('#challengeModal');
const startStopButton = document.querySelector('#startStopButton');
const runtimeStatus = document.querySelector('#runtimeStatus');
const flagStatus = document.querySelector('#flagStatus');

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const text = await response.text();
  let data = {};
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { message: text };
    }
  }
  if (!response.ok) {
    throw new Error(data.error || data.details || data.message || `Request failed with ${response.status}`);
  }
  return data;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;'
  }[character]));
}

function setStatus(element, message, type = '') {
  if (!element) return;
  element.textContent = message || '';
  element.className = `status ${type}`.trim();
}

async function loadSession() {
  try {
    const session = await request('/auth/me');
    state.user = session.user;
    document.querySelector('#userChip').textContent = `${state.user.username} / ${state.user.role}`;
    localStorage.setItem('kubebitCurrentUser', JSON.stringify(session.user));
  } catch {
    window.location.href = '/login';
  }
}

async function signOut() {
  await fetch('/auth/logout', { method: 'POST' });
  localStorage.removeItem('kubebitCurrentUser');
  window.location.href = '/login';
}

function saveRunning() {
  localStorage.setItem('kubebitRunning', JSON.stringify([...state.running.entries()]));
}

function hasContext() {
  return Boolean(state.user && state.user.id && state.user.team_id);
}

function categoryClass(category) {
  const normalized = String(category || 'misc').toLowerCase();
  if (normalized.includes('web')) return '#ede9fe';
  if (normalized.includes('crypto')) return '#fef3c7';
  if (normalized.includes('pwn')) return '#fee2e2';
  if (normalized.includes('rev')) return '#dbeafe';
  if (normalized.includes('docker') || normalized.includes('container')) return '#eef2ff';
  return '#e0f2fe';
}

function difficultyDots(points) {
  const level = points >= 450 ? 3 : points >= 250 ? 2 : 1;
  return [1, 2, 3].map(item => `<span class="dot ${item <= level ? 'active' : ''}"></span>`).join('');
}

function visibleChallenges() {
  if (!search) return state.challenges;
  const term = search.value.trim().toLowerCase();
  return state.challenges.filter(challenge => {
    const category = challenge.category_name || 'Uncategorized';
    const matchesCategory = state.activeCategory === 'all' || category === state.activeCategory;
    const text = `${challenge.name} ${challenge.description || ''} ${category}`.toLowerCase();
    return matchesCategory && (!term || text.includes(term));
  });
}

function renderFilters() {
  if (!filters) return;
  const categories = ['all', ...new Set(state.challenges.map(challenge => challenge.category_name || 'Uncategorized'))];
  filters.innerHTML = categories.map(category => `
    <button class="filter-pill ${category === state.activeCategory ? 'active' : ''}" data-category="${escapeHtml(category)}">
      ${category === 'all' ? 'All' : escapeHtml(category)}
    </button>
  `).join('');
}

function renderProgress() {
  const fill = document.querySelector('#progressFill');
  const count = document.querySelector('#progressCount');
  if (!fill || !count) return;
  const solved = state.teamSolved.size;
  const total = state.challenges.length;
  const percent = total ? Math.round((solved / total) * 100) : 0;
  fill.style.width = `${percent}%`;
  count.textContent = `${solved} / ${total} solved`;
}

function renderChallenges() {
  if (!grid) return;
  const challenges = visibleChallenges();
  renderProgress();
  if (!challenges.length) {
    grid.innerHTML = '<div class="empty">No tasks match the current filter.</div>';
    return;
  }

  grid.innerHTML = challenges.map(challenge => {
    const category = challenge.category_name || 'Uncategorized';
    const id = String(challenge.id);
    const isRunning = state.running.has(id);
    const isSolved = state.solved.has(id);
    const isTeamSolved = state.teamSolved.has(id);
    const isSolvedByTeammate = isTeamSolved && !isSolved;
    const solver = state.teamSolvedBy.get(id);
    const stateLabel = isSolved
      ? 'solved'
      : isSolvedByTeammate
        ? `solved by ${solver || 'team'}`
        : isRunning ? 'running' : challenge.type;

    return `
      <button class="challenge-card ${isRunning ? 'running' : ''} ${isSolved ? 'solved' : ''} ${isSolvedByTeammate ? 'team-solved' : ''}" data-id="${challenge.id}" type="button">
        <span class="category" style="background:${categoryClass(category)}">${escapeHtml(category)}</span>
        <span class="difficulty">${difficultyDots(challenge.base_points)}</span>
        <span class="challenge-name">${escapeHtml(challenge.name)}</span>
        <span class="challenge-desc">${escapeHtml(challenge.description || 'No description provided yet.')}</span>
        <span class="challenge-footer">
          <span class="points">${challenge.base_points} pts</span>
          <span class="card-state">${escapeHtml(stateLabel)}</span>
        </span>
      </button>
    `;
  }).join('');
}

function openChallenge(challenge) {
  if (!modal) return;
  const id = String(challenge.id);
  const category = challenge.category_name || 'Uncategorized';
  state.currentChallenge = challenge;

  document.querySelector('#modalTitle').textContent = challenge.name;
  document.querySelector('#modalDescription').textContent = challenge.description || 'No description provided yet.';
  document.querySelector('#modalMeta').innerHTML = `
    <span class="meta-pill">${escapeHtml(category)}</span>
    <span class="meta-pill">${challenge.base_points} pts</span>
    <span class="meta-pill">${escapeHtml(challenge.type)}</span>
    <span class="meta-pill">${challenge.max_attempts || 'unlimited'} attempts</span>
  `;

  const running = state.running.get(id);
  const isSolved = state.solved.has(id);
  const isTeamSolved = state.teamSolved.has(id);
  const solver = state.teamSolvedBy.get(id);
  const serviceDetails = running && (running.service_url || running.svc_name)
    ? `Service: ${running.service_url || running.svc_name}`
    : '';
  document.querySelector('#challengeUrl').classList.toggle('active', Boolean(serviceDetails));
  document.querySelector('#challengeUrl').textContent = serviceDetails;
  startStopButton.textContent = running ? 'Stop' : 'Start';
  startStopButton.className = running ? 'danger' : 'primary';
  setStatus(runtimeStatus, running ? 'Task is running.' : '');
  if (isSolved) {
    setStatus(flagStatus, 'You solved this task.', 'ok');
  } else if (isTeamSolved) {
    setStatus(flagStatus, `Solved by teammate${solver ? ` ${solver}` : ''}.`, 'warn');
  } else {
    setStatus(flagStatus, '');
  }
  document.querySelector('#flagInput').value = '';
  modal.classList.add('active');
}

async function toggleRuntime() {
  if (!state.currentChallenge) return;
  if (!hasContext()) {
    setStatus(runtimeStatus, 'You must belong to a team before starting tasks.', 'err');
    return;
  }

  const id = String(state.currentChallenge.id);
  const isRunning = state.running.has(id);
  const path = isRunning ? '/challenges/stop' : '/challenges/start';
  setStatus(runtimeStatus, isRunning ? 'Stopping task...' : 'Starting task...', 'warn');
  startStopButton.disabled = true;

  try {
    const result = await request(path, {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify({ challenge_id: state.currentChallenge.id })
    });

    if (isRunning) {
      state.running.delete(id);
      setStatus(runtimeStatus, 'Task stopped.', 'ok');
    } else {
      state.running.set(id, result);
      setStatus(runtimeStatus, 'Task started.', 'ok');
    }
    saveRunning();
    renderChallenges();
    openChallenge(state.currentChallenge);
  } catch (error) {
    setStatus(runtimeStatus, error.message, 'err');
  } finally {
    startStopButton.disabled = false;
  }
}

async function submitFlag(event) {
  event.preventDefault();
  if (!state.currentChallenge) return;
  if (!hasContext()) {
    setStatus(flagStatus, 'You must belong to a team before submitting flags.', 'err');
    return;
  }

  const flag = document.querySelector('#flagInput').value.trim();
  setStatus(flagStatus, 'Submitting flag...', 'warn');

  try {
    const result = await request(`/challenges/${state.currentChallenge.id}/submit`, {
      method: 'POST',
      headers: jsonHeaders,
      body: JSON.stringify({ flag })
    });

    if (result.correct && result.status !== 'already_solved') {
      state.solved.add(String(state.currentChallenge.id));
      state.teamSolved.add(String(state.currentChallenge.id));
      state.teamSolvedBy.set(String(state.currentChallenge.id), state.user ? state.user.username : null);
      renderChallenges();
      loadProfile();
      loadTeamSolves();
      loadTeam();
      setStatus(flagStatus, `Correct. ${result.points_awarded || state.currentChallenge.base_points} points awarded.`, 'ok');
      return;
    }

    if (result.status === 'already_solved') {
      state.teamSolved.add(String(state.currentChallenge.id));
      await loadTeamSolves();
      setStatus(flagStatus, 'This task is already solved by your team.', 'warn');
      return;
    }

    const attempts = result.attempts_left === null || result.attempts_left === undefined
      ? 'Incorrect flag.'
      : `Incorrect flag. ${result.attempts_left} attempts left.`;
    setStatus(flagStatus, attempts, 'err');
  } catch (error) {
    setStatus(flagStatus, error.message, 'err');
  }
}

async function loadChallenges() {
  if (!grid) return;
  try {
    state.challenges = await request('/challenges');
    renderFilters();
    renderChallenges();
  } catch (error) {
    grid.innerHTML = `<div class="empty">${escapeHtml(error.message)}</div>`;
  }
}

function rows(items, emptyText, render) {
  if (!items || items.length === 0) return `<tr><td class="empty" colspan="8">${emptyText}</td></tr>`;
  return items.map(render).join('');
}

function formatDate(value) {
  if (!value) return '-';
  return new Date(value).toLocaleString();
}

function renderProfile() {
  const stats = document.querySelector('#profileStats');
  const table = document.querySelector('#solvesTable');
  if (!stats || !table) return;
  const user = state.user || {};
  stats.innerHTML = `
    <div class="stat-row"><span>Username</span><strong>${escapeHtml(user.username || '-')}</strong></div>
    <div class="stat-row"><span>Name</span><strong>${escapeHtml(user.name || '-')}</strong></div>
    <div class="stat-row"><span>Team</span><strong>${escapeHtml(user.team_name || 'No team')}</strong></div>
    <div class="stat-row"><span>Points</span><strong>${user.points || 0}</strong></div>
    <div class="stat-row"><span>Solved</span><strong>${state.solves.length}</strong></div>
  `;

  table.innerHTML = rows(state.solves, 'No solved challenges yet.', solve => `
    <tr>
      <td><strong>${escapeHtml(solve.challenge_name)}</strong></td>
      <td>${escapeHtml(solve.category_name || '-')}</td>
      <td>${solve.points_awarded}</td>
      <td>${solve.is_first_blood ? '<span class="pill">yes</span>' : '-'}</td>
      <td>${escapeHtml(formatDate(solve.solved_at))}</td>
    </tr>
  `);
}

function renderTeam() {
  const stats = document.querySelector('#teamStats');
  const table = document.querySelector('#teamMembersTable');
  if (!stats || !table) return;
  const team = state.team;
  if (!team || !team.team_id) {
    stats.innerHTML = '<div class="stat-row"><span>Team</span><strong>No team assigned</strong></div>';
    table.innerHTML = '<tr><td colspan="5" class="empty">You are not assigned to a team yet.</td></tr>';
    return;
  }

  const totalPoints = team.users.reduce((sum, user) => sum + (user.points || 0), 0);
  stats.innerHTML = `
    <div class="stat-row"><span>Name</span><strong>${escapeHtml(team.team_name)}</strong></div>
    <div class="stat-row"><span>Members</span><strong>${team.users.length}</strong></div>
    <div class="stat-row"><span>Total points</span><strong>${totalPoints}</strong></div>
  `;

  table.innerHTML = rows(team.users, 'No team members yet.', user => `
    <tr>
      <td><strong>${escapeHtml(user.username)}</strong></td>
      <td>${escapeHtml(user.name)}</td>
      <td><span class="pill">${escapeHtml(user.role)}</span></td>
      <td>${user.is_captain ? 'yes' : '-'}</td>
      <td>${user.points}</td>
    </tr>
  `);
}

async function loadProfile() {
  const session = await request('/auth/me');
  state.user = session.user;
  document.querySelector('#userChip').textContent = `${state.user.username} / ${state.user.role}`;
  state.solves = await request('/me/solves');
  state.solved = new Set(state.solves.map(solve => String(solve.challenge_id)));
  renderProfile();
  renderChallenges();
}

async function loadTeamSolves() {
  state.teamSolves = await request('/me/team/solves');
  state.teamSolved = new Set(state.teamSolves.map(solve => String(solve.challenge_id)));
  state.teamSolvedBy = new Map(state.teamSolves.map(solve => [String(solve.challenge_id), solve.solver_username]));
  renderChallenges();
}

async function loadTeam() {
  state.team = await request('/me/team');
  renderTeam();
}

filters?.addEventListener('click', event => {
  const button = event.target.closest('[data-category]');
  if (!button) return;
  state.activeCategory = button.dataset.category;
  renderFilters();
  renderChallenges();
});

grid?.addEventListener('click', event => {
  const card = event.target.closest('[data-id]');
  if (!card) return;
  const challenge = state.challenges.find(item => String(item.id) === card.dataset.id);
  if (challenge) openChallenge(challenge);
});

search?.addEventListener('input', renderChallenges);
startStopButton?.addEventListener('click', toggleRuntime);
document.querySelector('#flagForm')?.addEventListener('submit', submitFlag);
document.querySelector('#signOutButton')?.addEventListener('click', signOut);
document.querySelector('#closeModal')?.addEventListener('click', () => modal?.classList.remove('active'));
modal?.addEventListener('click', event => {
  if (event.target === modal) modal.classList.remove('active');
});

loadSession().then(() => Promise.allSettled([loadChallenges(), loadProfile(), loadTeamSolves(), loadTeam()]));
