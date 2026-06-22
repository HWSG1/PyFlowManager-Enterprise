const data = window.PYFLOW_MANUAL_DATA;
const $ = selector => document.querySelector(selector);
const main = $('#main');
const nav = $('#nav');
const search = $('#search');
const searchInfo = $('#searchInfo');
const menuToggle = $('#menuToggle');
const menuClose = $('#menuClose');
const sidebarBackdrop = $('#sidebarBackdrop');

const sections = [
  ['overview', 'Resumen'],
  ['quickstart', 'Inicio rápido'],
  ['newfeatures', 'Funciones nuevas'],
  ['modules', 'Módulos'],
  ['governance', 'Gobierno por script'],
  ['deployment', 'Instalación y actualización'],
  ['settings', 'Parámetros por ambiente'],
  ['paramdict', 'Diccionario de parámetros'],
  ['access', 'Roles y permisos'],
  ['auth', 'Autenticación'],
  ['themes', 'Temas'],
  ['database', 'Base de datos'],
  ['troubleshooting', 'Errores comunes']
];

nav.innerHTML = `<div class="navgroup">Contenido</div>${sections.map(([id, label]) => `<a href="#${id}">${label}</a>`).join('')}`;

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
  }[character]));
}

function boolBadge(value) {
  return String(value) === '1' || value === true
    ? '<span class="badge ok">Activo</span>'
    : '<span class="badge warn">Inactivo</span>';
}

function secret(value, key, type) {
  return type === 'secret' || /PIN|PASSWORD|SECRET|TOKEN/i.test(String(key)) ? '********' : esc(value);
}

function envs() {
  return [...new Map(data.settings.map(setting => [
    String(setting.environment_id),
    { id: String(setting.environment_id), name: setting.environment_name || `Ambiente ${setting.environment_id}` }
  ])).values()].sort((a, b) => Number(a.id) - Number(b.id));
}

function renderOverview() {
  const release = data.release || {};
  return `<section id="overview" class="section hero searchable" data-keywords="manual resumen pyflow manager sistema scripts ejecuciones usuarios configuración">
    <p class="eyebrow">${esc(data.metadata?.version || 'Enterprise')} · Actualizado ${esc(data.metadata?.updatedAt || '')}</p>
    <h1>Manual PyFlow Manager</h1>
    <p>Guía operativa, técnica y de instalación. Explica cómo administrar scripts, ejecutar procesos, programar tareas, proteger accesos, recuperar versiones y diagnosticar problemas.</p>
    <div class="grid">
      <div class="kpi"><b>${envs().length}</b><span>Ambientes</span></div>
      <div class="kpi"><b>${(release.features || []).length}</b><span>Controles de gobierno</span></div>
      <div class="kpi"><b>${Object.keys(data.schema || {}).length}</b><span>Tablas documentadas</span></div>
    </div>
  </section>`;
}

function renderQuickstart() {
  return `<section id="quickstart" class="section card searchable" data-keywords="inicio rápido acceso login ejecutar script programación logs configuración">
    <h2>Inicio rápido</h2>
    <p class="muted">Recorrido recomendado para una primera operación segura.</p>
    <div class="step-list">
      <div class="step"><h3>Ingrese al sistema</h3><p>Use una cuenta activa con autenticación local o el proveedor corporativo habilitado.</p></div>
      <div class="step"><h3>Revise variables y ambiente</h3><p>Antes de ejecutar, confirme endpoints, rutas, credenciales globales y límites del ambiente.</p></div>
      <div class="step"><h3>Abra un script</h3><p>Complete únicamente los parámetros visibles. Las variables globales configuradas aparecen separadas al final.</p></div>
      <div class="step"><h3>Ejecute y supervise</h3><p>La consola muestra logs y progreso en tiempo real. Puede consultar parámetros e históricos desde <b>Ver log</b>.</p></div>
      <div class="step"><h3>Automatice</h3><p>Cuando la ejecución manual sea estable, cree una programación y valide la siguiente fecha calculada.</p></div>
    </div>
    <div class="note warning"><b>Consejo:</b> pruebe cambios de scripts con una versión nueva. No reemplace manualmente archivos dentro de <code>.versions</code>.</div>
  </section>`;
}

function renderNewFeatures() {
  const features = data.release?.features || [];
  return `<section id="newfeatures" class="section card">
    <h2>Funciones incorporadas</h2>
    <p class="muted">Capacidades disponibles en la versión actual y dónde administrarlas.</p>
    <div class="grid2">${features.map(feature => `<div class="result searchable" data-keywords="${esc(`${feature.title} ${feature.body} ${feature.location}`)}">
      <h3>${esc(feature.title)}</h3><p>${esc(feature.body)}</p><small><b>Ubicación:</b> ${esc(feature.location)}</small>
    </div>`).join('')}</div>
    <div class="note"><b>Reintentos persistentes:</b> si el backend se reinicia durante la espera, el trabajo permanece en SQL Server y se recupera desde la cola.</div>
  </section>`;
}

function renderModules() {
  return `<section id="modules" class="section card"><h2>Módulos del sistema</h2><p class="muted">Qué resuelve cada pantalla principal.</p>${data.modules.map(module => `<div class="result searchable" data-keywords="${esc(`${module.keywords} ${module.title} ${module.content}`)}"><h3>${esc(module.title)}</h3><p>${esc(module.content)}</p></div>`).join('')}</section>`;
}

function renderGovernance() {
  return `<section id="governance" class="section card searchable" data-keywords="gobierno reintentos alertas versiones rollback permisos auditoría script">
    <h2>Gobierno por script</h2>
    <p class="muted">Abra un script y utilice el panel <b>Gobierno y automatización</b>.</p>
    <div class="step-list">
      <div class="step"><h3>Política de ejecución</h3><p>Defina reintentos, espera inicial y factor de incremento. Con 3 reintentos, 60 segundos y factor 2, las esperas son 60, 120 y 240 segundos.</p></div>
      <div class="step"><h3>Alertas</h3><p>Active avisos de éxito o fallo final. Los destinatarios pueden separarse por coma, punto y coma o línea nueva.</p></div>
      <div class="step"><h3>Versiones</h3><p>Publique un <code>.py</code> con una versión única. La restauración valida el checksum y vuelve a sincronizar <code>PYFLOW_PARAMS</code>.</p></div>
      <div class="step"><h3>Accesos</h3><p>Asigne por usuario las capacidades Ver, Ejecutar, Editar y Programar. Sin asignaciones específicas se aplican los permisos generales del rol.</p></div>
      <div class="step"><h3>Auditoría</h3><p>En Configuración → Auditoría consulte cambios de scripts, usuarios, variables, programaciones, versiones y ejecuciones.</p></div>
    </div>
    <div class="note warning"><b>Microsoft Graph:</b> las alertas requieren <code>GRAPH_TENANT_ID</code>, <code>GRAPH_CLIENT_ID</code>, <code>GRAPH_CLIENT_SECRET</code> y <code>GRAPH_SENDER_EMAIL</code>.</div>
  </section>`;
}

function renderDeployment() {
  const options = data.release?.databaseOptions || [];
  return `<section id="deployment" class="section card searchable" data-keywords="instalación actualizar migración sql server 2019 2025 otra computadora base datos">
    <h2>Instalación y actualización</h2>
    <p class="muted">El procedimiento cambia según el estado de la base.</p>
    <div class="tablewrap"><table class="table"><thead><tr><th>Escenario</th><th>Archivo</th><th>Acción</th></tr></thead><tbody>${options.map(option => `<tr><td><b>${esc(option.scenario)}</b></td><td><code>${esc(option.file)}</code></td><td>${esc(option.action)}</td></tr>`).join('')}</tbody></table></div>
    <div class="step-list">
      <div class="step"><h3>Prepare el servidor</h3><p>Instale SQL Server, Node.js y Python. Conceda acceso a las carpetas de scripts, logs y exportaciones a la cuenta del backend.</p></div>
      <div class="step"><h3>Prepare la base</h3><p>Para una base nueva use un solo instalador. Para una base existente use únicamente la migración y realice un respaldo.</p></div>
      <div class="step"><h3>Complete snapshots</h3><pre class="code">cd backend\nnpm install\nnpm run migrate:governance</pre><p>El comando es idempotente y registra snapshots iniciales de scripts existentes.</p></div>
      <div class="step"><h3>Configure el backend</h3><pre class="code">DB_SERVER=servidor-sql\nDB_PORT=1433\nDB_DATABASE=PyFlowManager\nDB_USER=pyflow_user\nDB_PASSWORD=contraseña-segura</pre></div>
      <div class="step"><h3>Compile</h3><pre class="code">cd backend && npm run build\ncd ../frontend && npm run build</pre></div>
    </div>
    <div class="note danger"><b>No ejecute el instalador completo sobre una base existente.</b> Los instaladores 2019 y 2025 están preparados para una base nueva.</div>
  </section>`;
}

function renderSettings() {
  const environments = envs();
  return `<section id="settings" class="section card"><h2>Parámetros por ambiente</h2><p class="muted">Seleccione un ambiente para reducir la lista. Los secretos siempre aparecen enmascarados.</p>
    <div class="tabs">${environments.map((environment, index) => `<button class="tab ${index === 0 ? 'active' : ''}" type="button" data-env-button="${environment.id}">${esc(environment.name)}</button>`).join('')}<button class="tab" type="button" data-env-button="all">Todos</button></div>
    <div id="settingsList">${data.settings.map(setting => `<div class="result searchable setting-item" data-env="${esc(setting.environment_id)}" data-keywords="${esc([setting.environment_name, setting.setting_key, setting.setting_value, setting.setting_type, setting.category, setting.manual_description].join(' '))}">
      <div class="setting-card"><div><h3>${esc(setting.setting_key)} ${setting.is_critical === '1' ? '<span class="badge warn">Crítico</span>' : ''}</h3><p>${esc(setting.manual_description)}</p><div class="pillbar"><span class="badge">${esc(setting.environment_name)}</span><span class="badge">${esc(setting.category || 'general')}</span><span class="badge">${esc(setting.setting_type || 'string')}</span></div></div><div class="setting-value">${secret(setting.display_value, setting.setting_key, setting.setting_type)}</div></div>
    </div>`).join('')}</div>
  </section>`;
}

function renderParamDict() {
  const keys = [...new Set(data.settings.map(setting => setting.setting_key))].sort();
  return `<section id="paramdict" class="section card"><h2>Diccionario de parámetros</h2><p class="muted">Explicación funcional y valores por ambiente.</p>${keys.map(key => {
    const doc = data.paramDocs[key] || {};
    const rows = data.settings.filter(setting => setting.setting_key === key);
    return `<details class="result searchable" data-keywords="${esc(`${key} ${doc.title || ''} ${doc.desc || ''} ${rows.map(row => `${row.environment_name} ${row.setting_value}`).join(' ')}`)}"><summary><b>${esc(key)}</b> <span class="badge">${esc(doc.category || 'general')}</span></summary><p>${esc(doc.desc || rows[0]?.manual_description || 'Parámetro del sistema.')}</p><div class="tablewrap"><table class="table"><thead><tr><th>Ambiente</th><th>Valor</th><th>Tipo</th><th>Crítico</th></tr></thead><tbody>${rows.map(row => `<tr><td>${esc(row.environment_name)}</td><td><code>${secret(row.display_value, row.setting_key, row.setting_type)}</code></td><td>${esc(row.setting_type)}</td><td>${row.is_critical === '1' ? 'Sí' : 'No'}</td></tr>`).join('')}</tbody></table></div></details>`;
  }).join('')}</section>`;
}

function renderAccess() {
  return `<section id="access" class="section card"><h2>Roles y permisos</h2><div class="grid2"><div><h3>Roles</h3><div class="tablewrap"><table class="table"><thead><tr><th>Rol</th><th>Descripción</th><th>Método</th></tr></thead><tbody>${data.roles.map(role => `<tr class="searchable" data-keywords="${esc(Object.values(role).join(' '))}"><td>${esc(role.role_name)}</td><td>${esc(role.description)}</td><td>${esc(role.auth_method)}</td></tr>`).join('')}</tbody></table></div></div><div><h3>Permisos</h3><div class="tablewrap"><table class="table"><thead><tr><th>Permiso</th><th>Módulo</th><th>Acción</th><th>Descripción</th></tr></thead><tbody>${data.permissions.map(permission => `<tr class="searchable" data-keywords="${esc(Object.values(permission).join(' '))}"><td><code>${esc(permission.permission_key)}</code></td><td>${esc(permission.module_key)}</td><td>${esc(permission.action_key)}</td><td>${esc(permission.description)}</td></tr>`).join('')}</tbody></table></div></div></div><div class="note"><b>Regla:</b> el rol concede el permiso general y <code>ScriptAccess</code> lo restringe para un script específico.</div></section>`;
}

function renderAuth() {
  return `<section id="auth" class="section card searchable" data-keywords="autenticación login local entra azure ad mixed pbkdf2 password hash recuperación contraseña"><h2>Autenticación</h2><div class="grid2">${data.authMethods.map(method => `<div class="result"><h3>${esc(method.method_name)}</h3><p><b>Clave:</b> <code>${esc(method.method_key)}</code></p>${boolBadge(method.is_enabled)}</div>`).join('')}</div><div class="result"><h3>Contraseñas locales</h3><p>Formato esperado:</p><pre class="code">pbkdf2$120000$salt$hash</pre></div><div class="result"><h3>Microsoft Entra ID</h3><p>Requiere registrar la aplicación, configurar Tenant ID, Client ID, URI de redirección y completar el callback que genera el JWT interno.</p></div></section>`;
}

function renderThemes() {
  return `<section id="themes" class="section card"><h2>Temas visuales</h2><p class="muted">La selección se guarda como preferencia del usuario.</p><div class="grid">${data.themes.map(theme => `<div class="result searchable" data-keywords="${esc(Object.values(theme).join(' '))}"><h3>${esc(theme.theme_name)}</h3><p><code>${esc(theme.theme_key)}</code></p><span class="badge ${theme.is_dark === '1' ? 'dark' : 'light'}">${theme.is_dark === '1' ? 'Oscuro' : 'Claro'}</span> ${boolBadge(theme.is_enabled)}</div>`).join('')}</div></section>`;
}

function renderDatabase() {
  const names = Object.keys(data.schema || {}).sort();
  return `<section id="database" class="section card"><h2>Diccionario de base de datos</h2><p class="muted">Tablas y columnas utilizadas por la versión actual.</p>${names.map(name => {
    const columns = data.schema[name] || [];
    return `<details class="result searchable" data-keywords="${esc(`${name} ${data.tableDescriptions[name] || ''} ${columns.map(column => `${column.name} ${column.type}`).join(' ')}`)}"><summary><b>${esc(name)}</b> <span class="muted">(${columns.length} columnas)</span></summary><p>${esc(data.tableDescriptions[name] || 'Tabla del sistema PyFlow Manager.')}</p><div class="tablewrap"><table class="table"><thead><tr><th>Columna</th><th>Tipo</th><th>Nulo</th><th>Identity</th></tr></thead><tbody>${columns.map(column => `<tr><td>${esc(column.name)}</td><td>${esc(column.type)}</td><td>${column.nullable ? 'Sí' : 'No'}</td><td>${column.identity ? 'Sí' : 'No'}</td></tr>`).join('')}</tbody></table></div></details>`;
  }).join('')}</section>`;
}

function renderTroubleshooting() {
  return `<section id="troubleshooting" class="section card"><h2>Errores comunes</h2>${data.troubles.map(item => `<div class="result searchable" data-keywords="${esc(`${item.title} ${item.body}`)}"><h3>${esc(item.title)}</h3><p>${esc(item.body)}</p></div>`).join('')}</section>`;
}

function render() {
  main.innerHTML = renderOverview() + renderQuickstart() + renderNewFeatures() + renderModules() + renderGovernance() + renderDeployment() + renderSettings() + renderParamDict() + renderAccess() + renderAuth() + renderThemes() + renderDatabase() + renderTroubleshooting();
}

function filterEnvironment(environment, button) {
  document.querySelectorAll('[data-env-button]').forEach(item => item.classList.toggle('active', item === button));
  document.querySelectorAll('.setting-item').forEach(item => item.classList.toggle('hidden', environment !== 'all' && item.dataset.env !== environment));
}

function setMenu(open) {
  document.body.classList.toggle('menu-open', open);
  menuToggle?.setAttribute('aria-expanded', String(open));
  if (sidebarBackdrop) sidebarBackdrop.hidden = !open;
  if (open) search?.focus();
}

function updateActiveLink(id) {
  document.querySelectorAll('.nav a').forEach(link => link.classList.toggle('active', link.getAttribute('href') === `#${id}`));
}

render();

document.querySelectorAll('[data-env-button]').forEach(button => button.addEventListener('click', () => filterEnvironment(button.dataset.envButton, button)));

search.addEventListener('input', event => {
  const query = event.target.value.toLowerCase().trim();
  let shown = 0;
  document.querySelectorAll('.searchable').forEach(item => {
    const text = `${item.dataset.keywords || ''} ${item.innerText}`.toLowerCase();
    const match = !query || text.includes(query);
    item.classList.toggle('hidden', !match);
    if (match) shown++;
  });
  searchInfo.textContent = query ? `${shown} resultado(s) para “${query}”` : '';
});

menuToggle?.addEventListener('click', () => setMenu(true));
menuClose?.addEventListener('click', () => setMenu(false));
sidebarBackdrop?.addEventListener('click', () => setMenu(false));
document.addEventListener('keydown', event => { if (event.key === 'Escape') setMenu(false); });
nav.addEventListener('click', event => {
  const link = event.target.closest('a');
  if (!link) return;
  updateActiveLink(link.getAttribute('href').slice(1));
  if (window.matchMedia('(max-width: 760px)').matches) setMenu(false);
});

const observer = new IntersectionObserver(entries => {
  const visible = entries.filter(entry => entry.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
  if (visible) updateActiveLink(visible.target.id);
}, { rootMargin: '-15% 0px -70% 0px', threshold: [0, .2, .5] });
document.querySelectorAll('main > section').forEach(section => observer.observe(section));
updateActiveLink(location.hash.slice(1) || 'overview');
