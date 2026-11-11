// Receita Segura — front-end
// Conversa com a API FastAPI em /api (servidor em backend/main.py). PWA: service-worker.js.

const estado = {
  papel: 'medico',
  usuario: null,
  pacientes: [],
  receitas: [],
  catalogo: [],
  proximoIdMedicamento: 1
};

const CREDENCIAIS_DEMO = {
  medico: { email: 'camila@clinica.com', senha: 'demo123' },
  paciente: { email: 'joao@email.com', senha: 'demo123' }
};

const $ = (seletor) => document.querySelector(seletor);
const $$ = (seletor) => document.querySelectorAll(seletor);

// Evita que nomes/textos digitados virem HTML na página (proteção contra XSS).
const escapar = (texto) => String(texto ?? '').replace(/[&<>"']/g, c => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
));

const iniciais = (nome) => nome.replace(/^(Dra?\.)\s+/i, '').split(/\s+/).filter(Boolean)
  .map(p => p[0]).slice(0, 2).join('').toUpperCase();

const STATUS = {
  ativa: { texto: '✓ assinada', classe: '' },
  dispensada: { texto: '✓ dispensada', classe: 'status-dispensada' },
  cancelada: { texto: '✕ cancelada', classe: 'status-cancelada' }
};

const formatarData = (iso) => iso ? iso.slice(0, 10).split('-').reverse().join('/') : '—';
const formatarDataHora = (iso) => {
  const d = new Date(iso);
  return d.toLocaleDateString('pt-BR') + ' ' + d.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
};

// ---------- Comunicação com a API ----------

const CHAVE_TOKEN = 'receita-segura-token';
const lerToken = () => { try { return localStorage.getItem(CHAVE_TOKEN); } catch { return null; } };
const salvarToken = (token) => {
  try { token ? localStorage.setItem(CHAVE_TOKEN, token) : localStorage.removeItem(CHAVE_TOKEN); } catch { /* sem storage */ }
};

async function api(caminho, { metodo = 'GET', corpo } = {}) {
  const cabecalhos = { 'Content-Type': 'application/json' };
  const token = lerToken();
  if (token) cabecalhos.Authorization = `Bearer ${token}`;

  let resposta;
  try {
    resposta = await fetch(`/api${caminho}`, {
      method: metodo,
      headers: cabecalhos,
      body: corpo ? JSON.stringify(corpo) : undefined
    });
  } catch {
    throw new Error('Não foi possível falar com o servidor. Ele está rodando (iniciar.bat)?');
  }

  if (resposta.status === 204) return null;
  const dados = await resposta.json().catch(() => ({}));
  if (resposta.status === 401 && lerToken() && caminho !== '/auth/login') sair();
  if (!resposta.ok) throw new Error(dados.erro || 'Algo deu errado. Tente novamente.');
  return dados;
}

// ---------- Menu e navegação ----------

const botaoMenu = $('#botao-menu');
const menuMobile = $('#menu-mobile');
botaoMenu.addEventListener('click', () => {
  const aberto = menuMobile.classList.toggle('ativo');
  botaoMenu.setAttribute('aria-expanded', String(aberto));
});
$$('#menu-mobile a').forEach(a => a.addEventListener('click', () => {
  menuMobile.classList.remove('ativo');
  botaoMenu.setAttribute('aria-expanded', 'false');
}));

const telaAuth = $('#tela-auth');
const sitePublico = $('#site-publico');

function abrirAuth(papelPreferido) {
  sitePublico.classList.add('oculto');
  telaAuth.classList.remove('oculto');
  if (papelPreferido) selecionarPapel(papelPreferido);
  window.scrollTo(0, 0);
}

function fecharAuth() {
  telaAuth.classList.add('oculto');
  sitePublico.classList.remove('oculto');
  $('#erro-login').classList.add('oculto');
  $('#form-login').reset();
  mostrarFormAtivar(false);
}

$$('[data-abrir-auth]').forEach(el => {
  el.addEventListener('click', () => {
    menuMobile.classList.remove('ativo');
    abrirAuth(el.getAttribute('data-abrir-auth') || null);
  });
});
$('[data-fechar-auth]').addEventListener('click', fecharAuth);

// ---------- Login ----------

function selecionarPapel(papel) {
  estado.papel = papel;
  $$('.alternador button').forEach(b => b.classList.toggle('ativo', b.dataset.papel === papel));
  const cred = CREDENCIAIS_DEMO[papel];
  $('#credenciais-demo').innerHTML = papel === 'medico'
    ? `Demonstração — médico(a): <code>${cred.email}</code> / <code>${cred.senha}</code>`
    : `Demonstração — paciente: <code>${cred.email}</code> / <code>${cred.senha}</code>`;
  $('#erro-login').classList.add('oculto');
  $('#botao-primeiro-acesso').classList.toggle('oculto', papel !== 'paciente');
  mostrarFormAtivar(false);
}

$$('.alternador button').forEach(botao => {
  botao.addEventListener('click', () => selecionarPapel(botao.dataset.papel));
});

function mostrarErro(seletor, mensagem) {
  const el = $(seletor);
  el.textContent = mensagem;
  el.classList.remove('oculto');
}

$('#form-login').addEventListener('submit', async (evento) => {
  evento.preventDefault();
  const botao = evento.currentTarget.querySelector('[type=submit]');
  botao.disabled = true;
  try {
    const { token, usuario } = await api('/auth/login', {
      metodo: 'POST',
      corpo: { email: $('#email-login').value, senha: $('#senha-login').value, papel: estado.papel }
    });
    salvarToken(token);
    $('#erro-login').classList.add('oculto');
    $('#form-login').reset();
    await entrar(usuario);
  } catch (erro) {
    mostrarErro('#erro-login', erro.message);
  } finally {
    botao.disabled = false;
  }
});

// Primeiro acesso do paciente (código de convite gerado pelo médico)
function mostrarFormAtivar(mostrar) {
  $('#form-ativar').classList.toggle('oculto', !mostrar);
  $('#form-login').classList.toggle('oculto', mostrar);
  $('#credenciais-demo').classList.toggle('oculto', mostrar);
  $('#botao-primeiro-acesso').classList.toggle('oculto', mostrar || estado.papel !== 'paciente');
  $('#erro-ativar').classList.add('oculto');
}
$('#botao-primeiro-acesso').addEventListener('click', () => mostrarFormAtivar(true));
$('#voltar-login').addEventListener('click', () => mostrarFormAtivar(false));

$('#form-ativar').addEventListener('submit', async (evento) => {
  evento.preventDefault();
  const botao = evento.currentTarget.querySelector('[type=submit]');
  botao.disabled = true;
  try {
    const { token, usuario } = await api('/auth/ativar', {
      metodo: 'POST',
      corpo: { codigo: $('#codigo-ativar').value, email: $('#email-ativar').value, senha: $('#senha-ativar').value }
    });
    salvarToken(token);
    $('#form-ativar').reset();
    mostrarFormAtivar(false);
    await entrar(usuario);
  } catch (erro) {
    mostrarErro('#erro-ativar', erro.message);
  } finally {
    botao.disabled = false;
  }
});

// ---------- Painéis ----------

const painelMedico = $('#painel-medico');
const painelPaciente = $('#painel-paciente');

function fecharTodosPaineis() {
  painelMedico.classList.remove('ativo');
  painelPaciente.classList.remove('ativo');
}

async function entrar(usuario) {
  estado.usuario = usuario;
  telaAuth.classList.add('oculto');
  sitePublico.classList.add('oculto');
  if (usuario.papel === 'medico') await abrirPainelMedico();
  else await abrirPainelPaciente();
}

async function abrirPainelMedico() {
  const u = estado.usuario;
  $('#medico-avatar').textContent = iniciais(u.nome);
  $('#medico-nome').textContent = u.nome;
  $('#medico-info').textContent = [u.crm && `CRM ${u.crm}`, u.especialidade].filter(Boolean).join(' · ');
  $('#medico-saudacao').textContent = `Bem-vindo(a), ${u.nome}`;

  fecharTodosPaineis();
  painelMedico.classList.add('ativo');
  window.scrollTo(0, 0);
  await Promise.all([carregarPacientes(), carregarReceitas(), carregarCatalogo(), carregarHistoricoEAtividade()]);
}

async function abrirPainelPaciente() {
  const u = estado.usuario;
  $('#paciente-avatar').textContent = iniciais(u.nome);
  $('#paciente-nome').textContent = u.nome;
  $('#paciente-saudacao').textContent = `Olá, ${u.nome.split(' ')[0]}`;

  fecharTodosPaineis();
  painelPaciente.classList.add('ativo');
  window.scrollTo(0, 0);
  await Promise.all([carregarReceitas(), carregarHistoricoEAtividade()]);
}

async function sair() {
  const token = lerToken();
  salvarToken(null);
  if (token) fetch('/api/auth/logout', { method: 'POST', headers: { Authorization: `Bearer ${token}` } }).catch(() => {});
  estado.usuario = null;
  estado.pacientes = [];
  estado.receitas = [];
  fecharTodosPaineis();
  sitePublico.classList.remove('oculto');
  window.scrollTo(0, 0);
}

$$('[data-sair]').forEach(botao => botao.addEventListener('click', sair));

// ---------- Pacientes (médico) ----------

async function carregarPacientes() {
  try {
    const { pacientes } = await api('/pacientes');
    estado.pacientes = pacientes;
    renderizarPacientes();
    if (pacientes.length && !$('#paciente-receita-id').value) selecionarPaciente(pacientes[0].id);
  } catch (erro) {
    $('#lista-pacientes').innerHTML = `<p class="mensagem-erro">${escapar(erro.message)}</p>`;
  }
}

function renderizarPacientes() {
  const selecionado = Number($('#paciente-receita-id').value);
  $('#lista-pacientes').innerHTML = estado.pacientes.map(p => `
    <li><button type="button" data-paciente-id="${p.id}" class="${p.id === selecionado ? 'selecionado' : ''}">
      <strong>${escapar(p.nome)}</strong>
      <span>${p.ultimoAtendimento ? `Último atendimento: ${formatarData(p.ultimoAtendimento)}` : 'Novo paciente'}${p.contaAtiva ? '' : ' · sem conta'}</span>
    </button></li>
  `).join('') || '<p style="color:var(--cinza-700);font-size:0.9rem;">Nenhum paciente ainda.</p>';
}

function selecionarPaciente(id) {
  const paciente = estado.pacientes.find(p => p.id === id);
  if (!paciente) return;
  $('#paciente-receita-id').value = paciente.id;
  $('#paciente-receita').value = paciente.nome;
  renderizarPacientes();

  const convite = $('#convite-paciente');
  if (paciente.codigoConvite) {
    convite.innerHTML = `Código de primeiro acesso de <strong>${escapar(paciente.nome)}</strong>: <code>${escapar(paciente.codigoConvite)}</code><br>Entregue ao paciente para ele criar a conta e ver as receitas.`;
    convite.classList.remove('oculto');
  } else {
    convite.classList.add('oculto');
  }
}

$('#lista-pacientes').addEventListener('click', (evento) => {
  const botao = evento.target.closest('[data-paciente-id]');
  if (botao) selecionarPaciente(Number(botao.dataset.pacienteId));
});

const botaoNovoPaciente = $('#botao-novo-paciente');
const formNovoPaciente = $('#novo-paciente-form');
const inputNovoPaciente = $('#novo-paciente-nome');

botaoNovoPaciente.addEventListener('click', () => {
  formNovoPaciente.classList.remove('oculto');
  botaoNovoPaciente.classList.add('oculto');
  inputNovoPaciente.focus();
});

function fecharFormNovoPaciente() {
  formNovoPaciente.classList.add('oculto');
  botaoNovoPaciente.classList.remove('oculto');
  inputNovoPaciente.value = '';
}

$('#cancelar-novo-paciente').addEventListener('click', fecharFormNovoPaciente);
$('#confirmar-novo-paciente').addEventListener('click', adicionarNovoPaciente);
inputNovoPaciente.addEventListener('keydown', (evento) => {
  if (evento.key === 'Enter') {
    evento.preventDefault();
    adicionarNovoPaciente();
  }
});

async function adicionarNovoPaciente() {
  const nome = inputNovoPaciente.value.trim();
  if (!nome) return;
  try {
    const { paciente } = await api('/pacientes', { metodo: 'POST', corpo: { nome } });
    estado.pacientes.unshift(paciente);
    fecharFormNovoPaciente();
    selecionarPaciente(paciente.id);
  } catch (erro) {
    alert(erro.message);
  }
}

// ---------- Nova receita ----------

function novaLinhaMedicamento(nome = '', posologia = '') {
  const id = estado.proximoIdMedicamento++;
  const div = document.createElement('div');
  div.className = 'linha-medicamento';
  div.dataset.id = id;
  div.innerHTML = `
    <div class="campo" style="margin-bottom:0;">
      <label>Medicamento</label>
      <input type="text" class="campo-nome-medicamento" value="${escapar(nome)}" placeholder="Ex.: Amoxicilina 500mg" list="catalogo-medicamentos" autocomplete="off" required>
    </div>
    <div class="campo" style="margin-bottom:0;">
      <label>Posologia</label>
      <input type="text" class="campo-posologia-medicamento" value="${escapar(posologia)}" placeholder="Ex.: de 8 em 8h, por 7 dias" required>
    </div>
    <button type="button" class="botao-remover" aria-label="Remover medicamento">✕</button>
  `;
  div.querySelector('.botao-remover').addEventListener('click', () => div.remove());
  // Ao escolher um remédio do catálogo, preenche a posologia sugerida (se ainda estiver vazia).
  div.querySelector('.campo-nome-medicamento').addEventListener('change', (evento) => {
    const item = estado.catalogo?.find(m => m.nome === evento.target.value);
    const posologia = div.querySelector('.campo-posologia-medicamento');
    if (item && !posologia.value) posologia.value = item.posologiaSugerida;
  });
  $('#lista-medicamentos').appendChild(div);
}

$('#botao-adicionar-medicamento').addEventListener('click', () => novaLinhaMedicamento());
novaLinhaMedicamento('Amoxicilina 500mg', 'de 8 em 8h, por 7 dias');

const modalAssinar = $('#modal-assinar');
let receitaPendente = null;

$('#form-receita').addEventListener('submit', (evento) => {
  evento.preventDefault();
  $('#erro-receita').classList.add('oculto');
  const pacienteId = Number($('#paciente-receita-id').value);
  const medicamentos = [...$$('.linha-medicamento')].map(linha => ({
    nome: linha.querySelector('.campo-nome-medicamento').value.trim(),
    posologia: linha.querySelector('.campo-posologia-medicamento').value.trim()
  })).filter(m => m.nome);

  if (!pacienteId) return mostrarErro('#erro-receita', 'Selecione um paciente na lista.');
  if (medicamentos.length === 0) return mostrarErro('#erro-receita', 'Adicione pelo menos um medicamento.');

  receitaPendente = { pacienteId, medicamentos, orientacoes: $('#orientacoes').value.trim() };

  $('#resumo-receita').innerHTML = `
    <p><strong>Paciente:</strong> ${escapar($('#paciente-receita').value)}</p>
    <ul style="padding-left:18px;margin:10px 0;">
      ${medicamentos.map(m => `<li>${escapar(m.nome)} — ${escapar(m.posologia)}</li>`).join('')}
    </ul>
    ${receitaPendente.orientacoes ? `<p>${escapar(receitaPendente.orientacoes)}</p>` : ''}
  `;
  $('#selo-confirmado').classList.add('oculto');
  $('#botao-confirmar-assinatura').classList.remove('oculto');
  modalAssinar.classList.add('ativo');
});

// A assinatura acontece no servidor, com a chave privada do médico.
$('#botao-confirmar-assinatura').addEventListener('click', async (evento) => {
  if (!receitaPendente) return;
  const botao = evento.currentTarget;
  botao.disabled = true;
  try {
    const { receita } = await api('/receitas', { metodo: 'POST', corpo: receitaPendente });
    estado.receitas.unshift(receita);
    $('#selo-confirmado').classList.remove('oculto');
    botao.classList.add('oculto');
    renderizarReceitasEmitidas();
    carregarPacientes();
    carregarHistoricoEAtividade();

    setTimeout(() => {
      modalAssinar.classList.remove('ativo');
      $('#orientacoes').value = '';
      $('#lista-medicamentos').innerHTML = '';
      novaLinhaMedicamento();
      receitaPendente = null;
    }, 1400);
  } catch (erro) {
    modalAssinar.classList.remove('ativo');
    mostrarErro('#erro-receita', erro.message);
  } finally {
    botao.disabled = false;
  }
});

// ---------- Listas de receitas ----------

function formatarHashCurto(hash) {
  return hash.length > 12 ? `${hash.slice(0, 6)}…${hash.slice(-4)}` : hash;
}

async function carregarReceitas() {
  try {
    const { receitas } = await api('/receitas');
    estado.receitas = receitas;
  } catch (erro) {
    estado.receitas = [];
    console.error(erro);
  }
  if (estado.usuario?.papel === 'medico') renderizarReceitasEmitidas();
  else renderizarReceitasPaciente();
}

function renderizarLista(seletor, titulo, vazio) {
  const lista = $(seletor);
  lista.innerHTML = '';
  if (estado.receitas.length === 0) {
    lista.innerHTML = `<p style="color:var(--cinza-700);font-size:0.9rem;">${vazio}</p>`;
    return;
  }
  estado.receitas.forEach(receita => {
    const li = document.createElement('li');
    const botao = document.createElement('button');
    botao.className = 'item-receita';
    botao.innerHTML = `
      <span>
        <strong>${escapar(titulo(receita))}</strong>
        <span>#${escapar(receita.id)} · ${formatarDataHora(receita.emitidaEm)}</span>
      </span>
      <span class="assinado ${STATUS[receita.status]?.classe || ''}" style="white-space:nowrap;">${STATUS[receita.status]?.texto || '✓ assinada'}</span>
    `;
    botao.addEventListener('click', () => abrirDetalheReceita(receita));
    li.appendChild(botao);
    lista.appendChild(li);
  });
}

const renderizarReceitasEmitidas = () =>
  renderizarLista('#lista-emitidas', r => r.paciente, 'Nenhuma receita emitida ainda.');
const renderizarReceitasPaciente = () =>
  renderizarLista('#lista-paciente-receitas', r => r.medico, 'Nenhuma receita disponível ainda.');


// ---------- Catálogo de medicamentos (autocompletar) ----------

async function carregarCatalogo() {
  try {
    const { medicamentos } = await api('/medicamentos?limite=100');
    estado.catalogo = medicamentos;
    $('#catalogo-medicamentos').innerHTML = medicamentos
      .map(m => `<option value="${escapar(m.nome)}">${escapar(m.classe)}${m.controlado ? ' · controlado' : ''}</option>`)
      .join('');
  } catch (erro) {
    console.error(erro);
  }
}

// ---------- Histórico e auditoria ----------

async function carregarHistoricoEAtividade() {
  const prefixo = estado.usuario?.papel === 'medico' ? 'medico' : 'paciente';
  try {
    const [historico, { eventos }] = await Promise.all([api('/historico'), api('/auditoria?limite=8')]);
    const r = historico.resumo;
    const frequentes = historico.medicamentosMaisFrequentes.map(m => escapar(m.nome)).join(', ');
    $(`#${prefixo}-historico`).innerHTML = `
      <div class="resumo-historico">
        <div><strong>${r.total}</strong><span>receitas</span></div>
        <div><strong>${r.ativas}</strong><span>ativas</span></div>
        <div><strong>${r.dispensadas}</strong><span>dispensadas</span></div>
        <div><strong>${r.canceladas}</strong><span>canceladas</span></div>
      </div>
      ${frequentes ? `<p style="font-size:0.85rem;color:var(--cinza-700);margin-bottom:12px;"><strong>Mais prescritos:</strong> ${frequentes}</p>` : ''}
      <h3 style="font-size:0.9rem;margin:8px 0;">Atividade recente (auditoria)</h3>
    `;
    $(`#${prefixo}-atividade`).innerHTML = eventos.map(e => `
      <li>
        <span>${escapar(e.descricao)}${e.receita ? ` · #${escapar(e.receita)}` : ''}${e.usuario === 'Acesso público' ? ' · <em>acesso público</em>' : ''}</span>
        <time datetime="${escapar(e.quando)}">${formatarDataHora(e.quando)}</time>
      </li>
    `).join('') || '<li>Nenhuma atividade ainda.</li>';
  } catch (erro) {
    console.error(erro);
  }
}

// ---------- Detalhe da receita ----------

const modalDetalhe = $('#modal-detalhe');

// compartilhamento = token do link público (farmácia); sem ele, é o dono logado vendo a receita.
function abrirDetalheReceita(receita, { compartilhamento = null } = {}) {
  const ativa = receita.status === 'ativa';
  const souMedico = !compartilhamento && estado.usuario?.papel === 'medico';

  $('#conteudo-detalhe').innerHTML = `
    <div class="folha-receita" id="folha-atual">
      <div class="folha-topo">
        <div class="folha-marca">
          <img src="assets/logo.jpeg" alt="Receita Segura">
          <div>
            <strong>Receita Segura</strong>
            <span>receita médica digital</span>
          </div>
        </div>
        <span class="folha-rx">℞</span>
      </div>

      <div class="folha-corpo">
        <div class="folha-linha">
          <span><strong style="color:var(--tinta);">${escapar(receita.medico)}</strong><br>CRM ${escapar(receita.crm)}</span>
          <span style="text-align:right;">Receita #${escapar(receita.id)}<br>${formatarDataHora(receita.emitidaEm)}</span>
        </div>
        <div class="folha-linha" style="margin-bottom:0;">
          <span><strong style="color:var(--tinta);">Paciente:</strong> ${escapar(receita.paciente)}</span>
        </div>
      </div>

      <div class="folha-medicamentos">
        <h4>Medicamentos</h4>
        <ul>
          ${receita.medicamentos.map(m => `<li><strong>${escapar(m.nome)}</strong><span>${escapar(m.posologia)}</span></li>`).join('')}
        </ul>
      </div>

      ${receita.orientacoes ? `
      <div class="folha-orientacoes">
        <h4>Recomendações</h4>
        <p>${escapar(receita.orientacoes)}</p>
      </div>` : ''}

      <div class="folha-assinatura" id="bloco-assinatura">
        <span class="folha-selo" id="selo-verificacao">⏳ VERIFICANDO ASSINATURA…</span>
        <span class="folha-hash">SHA-256: ${escapar(formatarHashCurto(receita.hash))}</span>
      </div>

      <div class="folha-qr">
        <img src="/api/qrcode/${encodeURIComponent(receita.id)}.png" alt="QR Code de verificação da receita ${escapar(receita.id)}">
        <span>Aponte a câmera para o QR Code para conferir a autenticidade desta receita.${ativa ? '' : `<br><strong style="color:#b42318;">Receita ${escapar(receita.status)}${receita.statusMotivo ? ` — ${escapar(receita.statusMotivo)}` : ''}.</strong>`}</span>
      </div>

      <p class="folha-rodape-legal">Documento gerado pela plataforma Receita Segura — verificável pelo código #${escapar(receita.id)}. Protótipo acadêmico, não possui validade legal.</p>
    </div>

    <div class="acoes-receita">
      <button type="button" class="botao botao-primario" id="acao-pdf">📄 Baixar PDF</button>
      <button type="button" class="botao botao-secundario" onclick="window.print()">🖨️ Imprimir</button>
      ${!compartilhamento && ativa ? '<button type="button" class="botao botao-secundario largura-total" id="acao-compartilhar">🔗 Compartilhar com a farmácia</button>' : ''}
      ${compartilhamento ? '<button type="button" class="botao botao-secundario largura-total oculto" id="acao-dispensar">✓ Farmácia: marcar como dispensada</button>' : ''}
      ${souMedico && ativa ? '<button type="button" class="botao botao-perigo largura-total" id="acao-cancelar">Cancelar receita</button>' : ''}
    </div>
    <div id="resultado-acao"></div>
  `;
  modalDetalhe.classList.add('ativo');

  $('#acao-pdf').addEventListener('click', () => baixarPdf(receita.id, compartilhamento));
  $('#acao-compartilhar')?.addEventListener('click', () => compartilharReceita(receita.id));
  $('#acao-cancelar')?.addEventListener('click', () => cancelarReceita(receita.id));
  $('#acao-dispensar')?.addEventListener('click', () => dispensarReceita(compartilhamento));

  verificarAssinatura(receita.id);
}

// API de Verificação: o servidor recalcula o hash e confere a assinatura Ed25519.
async function verificarAssinatura(codigo) {
  const selo = $('#selo-verificacao');
  try {
    const resultado = await api(`/verificar/${encodeURIComponent(codigo)}`);
    if (!selo.isConnected) return;
    if (!resultado.valida) {
      selo.textContent = '✕ ASSINATURA INVÁLIDA — RECEITA ALTERADA';
      $('#bloco-assinatura').classList.add('invalida');
    } else {
      selo.textContent = resultado.status === 'ativa' ? '✓ ASSINATURA VERIFICADA' : `✓ ASSINATURA VÁLIDA · ${resultado.status.toUpperCase()}`;
    }
    $('#acao-dispensar')?.classList.toggle('oculto', !resultado.podeSerDispensada);
  } catch {
    if (selo.isConnected) selo.textContent = '✓ ASSINADO DIGITALMENTE';
  }
}

function mostrarResultadoAcao(html) {
  $('#resultado-acao').innerHTML = `<div class="caixa-link">${html}</div>`;
}

// API de PDF: o arquivo é gerado no servidor (precisa do token, por isso fetch + blob).
async function baixarPdf(codigo, compartilhamento) {
  const url = compartilhamento
    ? `/api/compartilhamentos/acesso/${encodeURIComponent(compartilhamento)}/pdf`
    : `/api/pdf/${encodeURIComponent(codigo)}`;
  try {
    const resposta = await fetch(url, { headers: lerToken() ? { Authorization: `Bearer ${lerToken()}` } : {} });
    if (!resposta.ok) throw new Error((await resposta.json().catch(() => ({}))).erro || 'Não foi possível gerar o PDF.');
    const link = document.createElement('a');
    link.href = URL.createObjectURL(await resposta.blob());
    link.download = `receita-${codigo}.pdf`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 10000);
  } catch (erro) {
    mostrarResultadoAcao(escapar(erro.message));
  }
}

// API de Compartilhamento: gera um link temporário (24h) para a farmácia.
async function compartilharReceita(codigo) {
  try {
    const { url, expiraEm } = await api('/compartilhamentos', { metodo: 'POST', corpo: { codigo, horas: 24 } });
    let copiado = false;
    try { await navigator.clipboard.writeText(url); copiado = true; } catch { /* sem permissão */ }
    mostrarResultadoAcao(`<strong>Link ${copiado ? 'copiado' : 'gerado'}!</strong> Válido até ${formatarDataHora(expiraEm)}.<br><a href="${escapar(url)}" target="_blank" rel="noopener">${escapar(url)}</a>`);
    carregarHistoricoEAtividade();
  } catch (erro) {
    mostrarResultadoAcao(escapar(erro.message));
  }
}

// API de Status: o médico cancela a receita (ela continua assinada, mas não pode mais ser usada).
async function cancelarReceita(codigo) {
  const motivo = prompt('Motivo do cancelamento:');
  if (!motivo || motivo.trim().length < 3) return;
  try {
    const { receita } = await api(`/status/receitas/${encodeURIComponent(codigo)}/cancelar`, { metodo: 'POST', corpo: { motivo } });
    estado.receitas = estado.receitas.map(r => (r.id === receita.id ? receita : r));
    renderizarReceitasEmitidas();
    carregarHistoricoEAtividade();
    abrirDetalheReceita(receita);
  } catch (erro) {
    mostrarResultadoAcao(escapar(erro.message));
  }
}

async function dispensarReceita(token) {
  if (!confirm('Confirmar que os medicamentos foram entregues? A receita não poderá ser usada de novo.')) return;
  try {
    const { receita } = await api(`/compartilhamentos/acesso/${encodeURIComponent(token)}/dispensar`, { metodo: 'POST' });
    abrirDetalheReceita(receita, { compartilhamento: token });
    mostrarResultadoAcao('<strong>Receita marcada como dispensada.</strong> O link foi desativado.');
  } catch (erro) {
    mostrarResultadoAcao(escapar(erro.message));
  }
}

// ---------- Telas públicas (sem login): QR Code e link compartilhado ----------

async function abrirVerificacaoPublica(codigo) {
  $('#conteudo-detalhe').innerHTML = '<p>Verificando…</p>';
  modalDetalhe.classList.add('ativo');
  try {
    const v = await api(`/verificar/${encodeURIComponent(codigo)}`);
    const titulo = !v.valida ? '✕ Assinatura inválida' : v.status === 'ativa' ? '✓ Assinatura verificada' : `⚠ Receita ${v.status}`;
    const cor = !v.valida || v.status === 'cancelada' ? 'style="background:#fde8e8;color:#b42318;"' : '';
    $('#conteudo-detalhe').innerHTML = `
      <div class="cartao-verificacao">
        <span class="status" ${cor}>${titulo}</span>
        <dl>
          <div class="linha-verificacao"><dt>Documento</dt><dd>Receita #${escapar(v.codigo)}</dd></div>
          <div class="linha-verificacao"><dt>Emitido por</dt><dd>${escapar(v.medico)}</dd></div>
          <div class="linha-verificacao"><dt>CRM</dt><dd>${escapar(v.crm)}</dd></div>
          <div class="linha-verificacao"><dt>Assinado em</dt><dd>${formatarDataHora(v.emitidaEm)}</dd></div>
          <div class="linha-verificacao"><dt>Situação</dt><dd>${escapar(v.status)}</dd></div>
          <div class="linha-verificacao"><dt>Hash (SHA-256)</dt><dd>${escapar(formatarHashCurto(v.hash))}</dd></div>
        </dl>
      </div>
      <p style="font-size:0.8rem;color:var(--cinza-700);margin-top:12px;">Por privacidade, medicamentos e paciente só aparecem para quem tem o link de compartilhamento.</p>
    `;
  } catch (erro) {
    $('#conteudo-detalhe').innerHTML = `<p class="mensagem-erro">${escapar(erro.message)}</p>`;
  }
}

async function abrirCompartilhamento(token) {
  try {
    const { receita } = await api(`/compartilhamentos/acesso/${encodeURIComponent(token)}`);
    abrirDetalheReceita(receita, { compartilhamento: token });
  } catch (erro) {
    $('#conteudo-detalhe').innerHTML = `<p class="mensagem-erro">${escapar(erro.message)}</p>`;
    modalDetalhe.classList.add('ativo');
  }
}

$$('[data-fechar-modal]').forEach(botao => {
  botao.addEventListener('click', () => {
    modalAssinar.classList.remove('ativo');
    modalDetalhe.classList.remove('ativo');
  });
});
$$('.sobreposicao').forEach(sobreposicao => {
  sobreposicao.addEventListener('click', (evento) => {
    if (evento.target === sobreposicao) sobreposicao.classList.remove('ativo');
  });
});
document.addEventListener('keydown', (evento) => {
  if (evento.key === 'Escape') {
    modalAssinar.classList.remove('ativo');
    modalDetalhe.classList.remove('ativo');
  }
});

// ---------- Início ----------

// PWA: registra o service worker (deixa o site instalável e disponível offline).
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/service-worker.js').catch(console.error));
}

(async () => {
  const parametros = new URLSearchParams(location.search);
  if (parametros.get('verificar')) return abrirVerificacaoPublica(parametros.get('verificar'));
  if (parametros.get('c')) return abrirCompartilhamento(parametros.get('c'));

  // Se já havia login salvo, volta direto para o painel.
  if (!lerToken()) return;
  try {
    const { usuario } = await api('/auth/eu');
    await entrar(usuario);
  } catch {
    salvarToken(null);
  }
})();
