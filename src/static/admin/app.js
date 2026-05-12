const jsonHeaders = { 'Content-Type': 'application/json' };
const adminState = { users: [], teams: [] };

function formData(form) {
  const data = {};
  new FormData(form).forEach((value, key) => {
    if (value === '') return;
    if (['user_id', 'team_id', 'captain_user_id', 'challenge_id', 'category_id', 'base_points', 'min_points', 'container_port', 'max_attempts'].includes(key)) {
      data[key] = Number(value);
    } else {
      data[key] = value;
    }
  });
  return data;
}

async function request(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `Request failed with ${response.status}`);
  }
  return payload;
}

function setStatus(form, message, kind = '') {
  const el = form.querySelector('[data-status]');
  if (!el) return;
  el.className = `status ${kind}`;
  el.textContent = message;
}

function rows(items, emptyText, render) {
  if (!items || items.length === 0) return `<tr><td class="empty" colspan="8">${emptyText}</td></tr>`;
  return items.map(render).join('');
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

async function loadSession() {
  try {
    const session = await request('/auth/me');
    const chip = document.querySelector('#userChip');
    if (chip) chip.textContent = `${session.user.username} / ${session.user.role}`;
  } catch {
    window.location.href = '/login';
  }
}

async function signOut() {
  await fetch('/auth/logout', { method: 'POST' });
  localStorage.removeItem('kubebitCurrentUser');
  window.location.href = '/login';
}

function refreshSelectOptions() {
  const userOptions = adminState.users.map(user => `
    <option value="${user.id}">${escapeHtml(user.username)} - ${escapeHtml(user.name)} (${escapeHtml(user.email)})</option>
  `).join('');
  const teamOptions = adminState.teams.map(team => `
    <option value="${team.id}">${escapeHtml(team.name)}${team.captain_username ? ` - captain ${escapeHtml(team.captain_username)}` : ''}</option>
  `).join('');

  document.querySelectorAll('[data-user-select]').forEach(select => {
    const current = select.value;
    const first = select.querySelector('option[value=""]')?.outerHTML || '<option value="">Choose user</option>';
    select.innerHTML = first + userOptions;
    select.value = current;
  });

  document.querySelectorAll('[data-team-select]').forEach(select => {
    const current = select.value;
    const first = select.querySelector('option[value=""]')?.outerHTML || '<option value="">Choose team</option>';
    select.innerHTML = first + teamOptions;
    select.value = current;
  });
}

async function loadUsers() {
  const users = await request('/users');
  adminState.users = users;
  refreshSelectOptions();

  const table = document.querySelector('#usersTable');
  if (!table) return;
  table.innerHTML = rows(users, 'No users yet.', user => `
    <tr>
      <td>${user.id}</td>
      <td><strong>${escapeHtml(user.username)}</strong></td>
      <td>${escapeHtml(user.name)}</td>
      <td>${escapeHtml(user.email)}</td>
      <td><span class="pill">${escapeHtml(user.role)}</span></td>
      <td>${escapeHtml(user.team_name || '-')}</td>
      <td>${user.points}</td>
    </tr>
  `);
}

async function loadTeams() {
  const teams = await request('/teams');
  adminState.teams = teams;
  refreshSelectOptions();

  const table = document.querySelector('#teamsTable');
  if (!table) return;
  table.innerHTML = rows(teams, 'No teams yet.', team => `
    <tr>
      <td>${team.id}</td>
      <td><strong>${escapeHtml(team.name)}</strong></td>
      <td>${escapeHtml(team.captain_username || '-')}</td>
      <td>${team.member_count}</td>
      <td>${team.points}</td>
    </tr>
  `);
}

async function loadCategories() {
  const table = document.querySelector('#categoriesTable');
  if (!table) return;
  const categories = await request('/categories');
  table.innerHTML = rows(categories, 'No categories yet.', category => `
    <tr><td>${category.id}</td><td><strong>${escapeHtml(category.name)}</strong></td></tr>
  `);
}

async function loadChallenges() {
  const table = document.querySelector('#challengesTable');
  if (!table) return;
  const challenges = await request('/challenges');
  table.innerHTML = rows(challenges, 'No challenges yet.', challenge => `
    <tr>
      <td>${challenge.id}</td>
      <td><strong>${escapeHtml(challenge.name)}</strong></td>
      <td><span class="pill">${escapeHtml(challenge.type)}</span></td>
      <td>${challenge.base_points}</td>
      <td>${escapeHtml(challenge.category_name || challenge.category_id)}</td>
    </tr>
  `);
}

async function loadTeamUsers(teamId) {
  const table = document.querySelector('#teamUsersTable');
  if (!table) return;
  const team = await request(`/teams/${teamId}/users`);
  table.innerHTML = rows(team.users, 'No users in this team.', user => `
    <tr>
      <td>${user.id}</td>
      <td><strong>${escapeHtml(user.username)}</strong></td>
      <td>${escapeHtml(user.name)}</td>
      <td>${escapeHtml(user.email)}</td>
      <td>${user.is_captain ? 'yes' : '-'}</td>
      <td>${user.points}</td>
    </tr>
  `);
}

async function refreshAll() {
  await Promise.allSettled([loadUsers(), loadTeams(), loadCategories(), loadChallenges()]);
}

async function checkAdminInitialization() {
  const overlay = document.querySelector('#setupOverlay');
  if (!overlay) return;
  const setup = await request('/admin/initialize-password/status');
  overlay.classList.toggle('active', setup.required);
}

document.querySelectorAll('[data-challenge-tab]').forEach(button => {
  button.addEventListener('click', () => {
    document.querySelectorAll('[data-challenge-tab]').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.challenge-form').forEach(form => form.classList.remove('active'));
    button.classList.add('active');
    document.querySelector(`#${button.dataset.challengeTab === 'container_static' ? 'containerStaticForm' : button.dataset.challengeTab + 'Form'}`).classList.add('active');
  });
});

document.querySelectorAll('[data-refresh]').forEach(button => {
  button.addEventListener('click', () => {
    const target = button.dataset.refresh;
    if (target === 'users') loadUsers();
    if (target === 'teams') loadTeams();
    if (target === 'categories') loadCategories();
    if (target === 'challenges') loadChallenges();
  });
});

document.querySelectorAll('form[data-action]').forEach(form => {
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const action = form.dataset.action;
    const data = formData(form);

    try {
      if (action === 'unsupported') {
        setStatus(form, 'Backend endpoint is not available yet.', 'warn');
        return;
      }
      if (action === 'initialize-admin') {
        if (data.password !== data.password_confirm) {
          setStatus(form, 'Passwords do not match.', 'err');
          return;
        }
        await request('/admin/initialize-password', { method: 'POST', headers: jsonHeaders, body: JSON.stringify(data) });
        setStatus(form, 'Admin password initialized.', 'ok');
        form.reset();
        document.querySelector('#setupOverlay')?.classList.remove('active');
      }
      if (action === 'create-user') {
        await request('/users', { method: 'POST', headers: jsonHeaders, body: JSON.stringify(data) });
        setStatus(form, 'User created.', 'ok');
        form.reset();
        await loadUsers();
      }
      if (action === 'create-team') {
        await request('/teams', { method: 'POST', headers: jsonHeaders, body: JSON.stringify(data) });
        setStatus(form, 'Team created.', 'ok');
        form.reset();
        await Promise.all([loadTeams(), loadUsers()]);
      }
      if (action === 'assign-user') {
        await request(`/teams/${data.team_id}/users`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ user_id: data.user_id }) });
        setStatus(form, 'User assigned.', 'ok');
        await Promise.all([loadTeams(), loadUsers()]);
      }
      if (action === 'assign-captain') {
        await request(`/teams/${data.team_id}/captain`, { method: 'POST', headers: jsonHeaders, body: JSON.stringify({ captain_user_id: data.captain_user_id }) });
        setStatus(form, 'Captain assigned.', 'ok');
        await Promise.all([loadTeams(), loadUsers()]);
      }
      if (action === 'load-team-users') {
        await loadTeamUsers(data.team_id);
        setStatus(form, 'Members loaded.', 'ok');
      }
      if (action === 'create-category') {
        await request('/admin/categories', { method: 'POST', headers: jsonHeaders, body: JSON.stringify(data) });
        setStatus(form, 'Category created.', 'ok');
        form.reset();
        await loadCategories();
      }
      if (action === 'create-container-challenge') {
        await request('/admin/challenges/container', { method: 'POST', headers: jsonHeaders, body: JSON.stringify(data) });
        setStatus(form, 'Container challenge created.', 'ok');
        form.reset();
        await loadChallenges();
      }
    } catch (error) {
      setStatus(form, error.message, 'err');
    }
  });
});

document.querySelector('#signOutButton')?.addEventListener('click', signOut);
checkAdminInitialization();
loadSession();
refreshAll();
