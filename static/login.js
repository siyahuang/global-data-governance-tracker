const form = document.querySelector('#auth-form');
const errorBox = document.querySelector('#form-error');
const switchButton = document.querySelector('#switch-mode');
const submitButton = document.querySelector('#submit-button');
let mode = 'login';
let allowRegistration = true;

async function setup() {
  const response = await fetch('/api/auth/config');
  const config = await response.json();
  allowRegistration = config.allow_registration;
  if (!allowRegistration) switchButton.hidden = true;
}

function renderMode() {
  const register = mode === 'register';
  document.querySelector('#form-title').textContent = register ? '创建访问账号' : '登录追踪器';
  document.querySelector('#form-note').textContent = register ? '注册后即可进入追踪器。' : '使用你的邮箱和密码继续。';
  submitButton.textContent = register ? '创建账号并登录' : '登录';
  switchButton.textContent = register ? '已有账号？返回登录' : '还没有账号？创建账号';
  document.querySelector('#password').autocomplete = register ? 'new-password' : 'current-password';
  errorBox.textContent = '';
}

switchButton.addEventListener('click', () => {
  if (!allowRegistration) return;
  mode = mode === 'login' ? 'register' : 'login';
  renderMode();
});

form.addEventListener('submit', async event => {
  event.preventDefault();
  submitButton.disabled = true;
  errorBox.textContent = '';
  try {
    const response = await fetch('/api/auth/' + mode, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email: form.email.value, password: form.password.value}),
    });
    const body = await response.json();
    if (!response.ok) throw new Error(body.error || '操作失败，请稍后再试');
    window.location.assign('/');
  } catch (error) {
    errorBox.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

setup().catch(() => { errorBox.textContent = '暂时无法连接服务，请稍后刷新。'; });
