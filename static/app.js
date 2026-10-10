const $ = (selector) => document.querySelector(selector);

async function api(url, options = {}) {
  const response = await fetch(url, {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Something went wrong. Please try again.');
  return data;
}

if (document.body.classList.contains('login-page')) {
  let login = true;
  const mode = () => {
    $('#account-title').textContent = login ? 'Sign in' : 'Create your account';
    $('#account-submit').innerHTML = `${login ? 'Sign in' : 'Create account'} <span aria-hidden="true">→</span>`;
    $('#account-mode').textContent = login ? 'New to Vortex? Create an account' : 'Already have an account? Sign in';
    $('#account-password').autocomplete = login ? 'current-password' : 'new-password';
    $('#account-intro').textContent = login
      ? 'Your conversations are saved to your account.'
      : 'Create an account to start chatting with Vortex AI.';
    $('#account-intro').classList.remove('error');
  };
  mode();
  $('#account-form').noValidate = true;
  $('#account-mode').addEventListener('click', () => { login = !login; mode(); });
  $('#account-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const username = $('#account-name').value.trim();
    const password = $('#account-password').value;
    if (!username) {
      $('#account-intro').textContent = 'Enter your username to continue.';
      $('#account-intro').classList.add('error');
      $('#account-name').focus();
      return;
    }
    if (!login && (username.length < 2 || username.length > 40)) {
      $('#account-intro').textContent = 'Choose a username between 2 and 40 characters.';
      $('#account-intro').classList.add('error');
      $('#account-name').focus();
      return;
    }
    if (password.length < 8) {
      $('#account-intro').textContent = 'Your password must be at least 8 characters.';
      $('#account-intro').classList.add('error');
      $('#account-password').focus();
      return;
    }
    const button = $('#account-submit');
    button.disabled = true;
    button.textContent = login ? 'Signing in…' : 'Creating account…';
    try {
      await api(login ? '/api/login' : '/api/register', {
        method: 'POST',
        body: JSON.stringify({
          username,
          password,
        }),
      });
      window.location.replace('/chat?start=1');
    } catch (error) {
      $('#account-intro').textContent = error.message;
      $('#account-intro').classList.add('error');
      button.disabled = false;
      mode();
    }
  });
} else {
  const chat = $('#chat');
  let activeChatId;

  function makeWelcome() {
    const wrapper = document.createElement('div');
    wrapper.className = 'welcome';
    wrapper.innerHTML = '<div class="welcome-mark" aria-hidden="true">✦</div><p class="eyebrow">VORTEX AI</p><h2>What’s on your mind?</h2><p>Ask anything, explore an idea, or get help with something you’re working on.</p><div class="welcome-hint"><span aria-hidden="true">⌕</span> Web and Wikipedia sources are checked automatically when useful.</div>';
    return wrapper;
  }

  function makeMessage(role, text, sources = []) {
    const template = $(role === 'user' ? '#user-template' : '#answer-template');
    const fragment = template.content.cloneNode(true);
    const article = fragment.querySelector('article');
    if (role === 'user') {
      article.querySelector('.message-body p').textContent = text;
    } else {
      article.querySelector('.answer-text').textContent = text;
      const sourceBox = article.querySelector('.sources');
      if (!sources.length) {
        sourceBox.remove();
      } else {
        const list = sourceBox.querySelector('ul');
        sources.forEach((source) => {
          const link = document.createElement('a');
          link.href = source.url;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          link.textContent = source.title;
          const item = document.createElement('li');
          item.append(link);
          list.append(item);
        });
      }
    }
    return fragment;
  }

  async function selectChat(conversation) {
    activeChatId = conversation.id;
    $('#chat-title').textContent = conversation.title;
    const data = await api(`/api/chats/${conversation.id}`);
    chat.replaceChildren();
    if (!data.messages.length) chat.append(makeWelcome());
    data.messages.forEach((message) => chat.append(makeMessage(message.role, message.text, message.sources)));
    await refreshChats();
    chat.scrollTop = chat.scrollHeight;
  }

  async function refreshChats() {
    const conversations = await api('/api/chats');
    const list = $('#chat-list');
    list.replaceChildren();
    conversations.forEach((conversation) => {
      const button = document.createElement('button');
      button.className = `chat-item${conversation.id === activeChatId ? ' active' : ''}`;
      button.textContent = conversation.title;
      button.type = 'button';
      button.addEventListener('click', () => selectChat(conversation));
      list.append(button);
    });
    return conversations;
  }

  async function newChat() {
    const conversation = await api('/api/chats', { method: 'POST' });
    await selectChat(conversation);
    $('#question').focus();
  }

  $('#new-chat').addEventListener('click', () => newChat().catch(showError));
  $('#sign-out').addEventListener('click', async () => {
    try {
      await api('/api/logout', { method: 'POST' });
      window.location.replace('/login');
    } catch (error) {
      showError(error);
    }
  });

  function showError(error) {
    chat.append(makeMessage('assistant', error.message || 'Something went wrong. Please try again.'));
    chat.scrollTop = chat.scrollHeight;
  }

  $('#question-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    const question = $('#question').value.trim();
    const sendButton = $('#send-button');
    if (!question || !activeChatId || sendButton.disabled) return;
    chat.querySelector('.welcome')?.remove();
    chat.append(makeMessage('user', question));
    $('#question').value = '';
    sendButton.disabled = true;
    sendButton.innerHTML = 'Thinking…';
    chat.scrollTop = chat.scrollHeight;
    try {
      const data = await api(`/api/chats/${activeChatId}/ask`, {
        method: 'POST',
        body: JSON.stringify({ question }),
      });
      chat.append(makeMessage('assistant', data.answer, data.sources));
      await refreshChats();
    } catch (error) {
      showError(error);
    } finally {
      sendButton.disabled = false;
      sendButton.innerHTML = 'Send <span aria-hidden="true">↑</span>';
      chat.scrollTop = chat.scrollHeight;
      $('#question').focus();
    }
  });

  (async () => {
    try {
      const account = await api('/api/me');
      if (!account.ai_enabled) {
        $('.online-pill').classList.add('needs-setup');
        $('.online-pill').innerHTML = '<span></span> AI setup needed';
        $('.composer-note').textContent = 'Web and Wikipedia results are available. Add an OpenAI API key in the hosting settings for full AI answers.';
      }
      if (new URLSearchParams(window.location.search).has('start')) {
        await newChat();
      } else {
        const conversations = await refreshChats();
        if (conversations.length) await selectChat(conversations[0]);
        else await newChat();
      }
    } catch (error) {
      showError(error);
    }
  })();
}

