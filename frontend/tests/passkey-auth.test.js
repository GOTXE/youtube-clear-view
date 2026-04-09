import { beforeEach, describe, expect, it, vi } from 'vitest';

describe('passkey browser helper', () => {
  beforeEach(() => {
    vi.resetModules();
    window.PublicKeyCredential = function PublicKeyCredential() {};
    navigator.credentials = {
      create: vi.fn(),
      get: vi.fn()
    };
  });

  it('registers a passkey through the browser ceremony and backend endpoints', async () => {
    await import('../js/passkey-auth.js');

    const rawId = Uint8Array.from([1, 2, 3]).buffer;
    navigator.credentials.create.mockResolvedValue({
      id: 'credential-1',
      rawId,
      type: 'public-key',
      response: {
        clientDataJSON: Uint8Array.from([4, 5, 6]).buffer,
        attestationObject: Uint8Array.from([7, 8, 9]).buffer,
        getTransports: () => ['internal']
      }
    });

    const api = {
      getPasskeyRegistrationOptions: vi.fn(async () => ({
        ok: true,
        data: {
          publicKey: {
            challenge: 'AQID',
            user: { id: 'BAUG', name: 'alice@example.com', displayName: 'Alice' }
          }
        }
      })),
      verifyPasskeyRegistration: vi.fn(async payload => ({ ok: true, data: payload }))
    };

    const response = await window.ytcvPasskeys.registerPasskey(api, 'Laptop');

    expect(api.getPasskeyRegistrationOptions).toHaveBeenCalledWith('Laptop');
    expect(navigator.credentials.create).toHaveBeenCalled();
    expect(api.verifyPasskeyRegistration).toHaveBeenCalled();
    expect(response.ok).toBe(true);
  });

  it('authenticates with an existing passkey through the browser ceremony', async () => {
    await import('../js/passkey-auth.js');

    navigator.credentials.get.mockResolvedValue({
      id: 'credential-2',
      rawId: Uint8Array.from([1, 2, 3]).buffer,
      type: 'public-key',
      response: {
        authenticatorData: Uint8Array.from([4, 5, 6]).buffer,
        clientDataJSON: Uint8Array.from([7, 8, 9]).buffer,
        signature: Uint8Array.from([10, 11, 12]).buffer,
        userHandle: Uint8Array.from([13, 14]).buffer
      }
    });

    const api = {
      getPasskeyAuthenticationOptions: vi.fn(async () => ({
        ok: true,
        data: { publicKey: { challenge: 'AQID' } }
      })),
      verifyPasskeyAuthentication: vi.fn(async payload => ({
        ok: true,
        data: payload
      }))
    };

    const response = await window.ytcvPasskeys.authenticateWithPasskey(api);

    expect(api.getPasskeyAuthenticationOptions).toHaveBeenCalled();
    expect(navigator.credentials.get).toHaveBeenCalled();
    expect(api.verifyPasskeyAuthentication).toHaveBeenCalled();
    expect(response.ok).toBe(true);
  });
});
