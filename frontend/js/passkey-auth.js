// WebAuthn/passkey browser helper for auth v2.

(() => {
  function isSupported() {
    return Boolean(
      window.PublicKeyCredential
      && navigator.credentials
      && typeof navigator.credentials.create === 'function'
      && typeof navigator.credentials.get === 'function'
    );
  }

  function base64UrlToArrayBuffer(value) {
    const normalized = `${value}`.replace(/-/g, '+').replace(/_/g, '/');
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=');
    const binary = window.atob(padded);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
      bytes[index] = binary.charCodeAt(index);
    }
    return bytes.buffer;
  }

  function arrayBufferToBase64Url(buffer) {
    const bytes = buffer instanceof Uint8Array ? buffer : new Uint8Array(buffer);
    let binary = '';
    bytes.forEach(byte => {
      binary += String.fromCharCode(byte);
    });
    return window.btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
  }

  function normalizeCreationOptions(publicKey) {
    const options = { ...publicKey };
    options.challenge = base64UrlToArrayBuffer(publicKey.challenge);
    options.user = { ...publicKey.user, id: base64UrlToArrayBuffer(publicKey.user.id) };
    if (Array.isArray(publicKey.excludeCredentials)) {
      options.excludeCredentials = publicKey.excludeCredentials.map(item => ({
        ...item,
        id: base64UrlToArrayBuffer(item.id)
      }));
    }
    return options;
  }

  function normalizeRequestOptions(publicKey) {
    const options = { ...publicKey };
    options.challenge = base64UrlToArrayBuffer(publicKey.challenge);
    if (Array.isArray(publicKey.allowCredentials)) {
      options.allowCredentials = publicKey.allowCredentials.map(item => ({
        ...item,
        id: base64UrlToArrayBuffer(item.id)
      }));
    }
    return options;
  }

  function serializeRegistrationCredential(credential) {
    const response = credential.response || {};
    const transports = typeof response.getTransports === 'function' ? response.getTransports() : [];
    return {
      id: credential.id,
      rawId: arrayBufferToBase64Url(credential.rawId),
      type: credential.type,
      response: {
        clientDataJSON: arrayBufferToBase64Url(response.clientDataJSON),
        attestationObject: arrayBufferToBase64Url(response.attestationObject)
      },
      transports
    };
  }

  function serializeAuthenticationCredential(credential) {
    const response = credential.response || {};
    return {
      id: credential.id,
      rawId: arrayBufferToBase64Url(credential.rawId),
      type: credential.type,
      response: {
        authenticatorData: arrayBufferToBase64Url(response.authenticatorData),
        clientDataJSON: arrayBufferToBase64Url(response.clientDataJSON),
        signature: arrayBufferToBase64Url(response.signature),
        userHandle: response.userHandle ? arrayBufferToBase64Url(response.userHandle) : null
      }
    };
  }

  function getErrorMessage(response, fallback) {
    if (response && response.error) {
      return response.error;
    }
    return fallback;
  }

  async function registerPasskey(api, label = '') {
    if (!isSupported()) {
      throw new Error('Passkeys are not supported in this browser.');
    }

    const optionsResponse = await api.getPasskeyRegistrationOptions(label);
    if (!optionsResponse.ok || !optionsResponse.data || !optionsResponse.data.publicKey) {
      throw new Error(getErrorMessage(optionsResponse, 'Unable to start passkey registration.'));
    }

    const credential = await navigator.credentials.create({
      publicKey: normalizeCreationOptions(optionsResponse.data.publicKey)
    });
    const serialized = serializeRegistrationCredential(credential);
    const verifyResponse = await api.verifyPasskeyRegistration({
      credential: serialized,
      label,
      transports: serialized.transports || []
    });
    if (!verifyResponse.ok) {
      throw new Error(getErrorMessage(verifyResponse, 'Unable to register passkey.'));
    }
    return verifyResponse;
  }

  async function authenticateWithPasskey(api) {
    if (!isSupported()) {
      throw new Error('Passkeys are not supported in this browser.');
    }

    const optionsResponse = await api.getPasskeyAuthenticationOptions();
    if (!optionsResponse.ok || !optionsResponse.data || !optionsResponse.data.publicKey) {
      throw new Error(getErrorMessage(optionsResponse, 'Unable to start passkey sign-in.'));
    }

    const credential = await navigator.credentials.get({
      publicKey: normalizeRequestOptions(optionsResponse.data.publicKey)
    });
    const verifyResponse = await api.verifyPasskeyAuthentication({
      credential: serializeAuthenticationCredential(credential)
    });
    if (!verifyResponse.ok) {
      throw new Error(getErrorMessage(verifyResponse, 'Unable to sign in with passkey.'));
    }
    return verifyResponse;
  }

  window.ytcvPasskeys = {
    isSupported,
    registerPasskey,
    authenticateWithPasskey
  };
})();
