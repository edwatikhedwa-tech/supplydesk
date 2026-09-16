import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../lib/api';
import { ContactResultModal } from './ContactResultModal';

vi.mock('../lib/api', () => ({
  api: { recordContactResult: vi.fn() },
  ApiError: class ApiError extends Error {
    status: number;
    constructor(status: number, message: string) {
      super(message);
      this.status = status;
    }
  },
}));

describe('ContactResultModal', () => {
  const onClose = vi.fn();
  const onSaved = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.recordContactResult).mockResolvedValue({ ok: true, event_id: 1, result: 'contact_confirmed', override_created: false });
  });

  function setup() {
    render(
      <ContactResultModal requestId={7} supplierId={42} supplierName="ООО Ромашка" onClose={onClose} onSaved={onSaved} />,
    );
  }

  it('defaults to "Контакт подтверждён" and saves without an email field', async () => {
    setup();
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
    await vi.waitFor(() => expect(api.recordContactResult).toHaveBeenCalledTimes(1));
    expect(api.recordContactResult).toHaveBeenCalledWith(7, 42, {
      result: 'contact_confirmed',
      comment: undefined,
      new_email: undefined,
    });
    expect(onSaved).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it('requires a new email address before saving when "Уточнён новый email" is selected', async () => {
    setup();
    fireEvent.click(screen.getByLabelText('Уточнён новый email'));
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
    expect(await screen.findByText('Укажите новый email поставщика.')).toBeInTheDocument();
    expect(api.recordContactResult).not.toHaveBeenCalled();
  });

  it('submits the new email once provided and reports the confirmed override to the caller', async () => {
    vi.mocked(api.recordContactResult).mockResolvedValue({ ok: true, event_id: 2, result: 'new_email_provided', override_created: true });
    setup();
    fireEvent.click(screen.getByLabelText('Уточнён новый email'));
    fireEvent.change(screen.getByPlaceholderText('new-contact@example.com'), { target: { value: 'sales@newmail.example' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
    await vi.waitFor(() => expect(api.recordContactResult).toHaveBeenCalledTimes(1));
    expect(api.recordContactResult).toHaveBeenCalledWith(7, 42, {
      result: 'new_email_provided',
      comment: undefined,
      new_email: 'sales@newmail.example',
    });
    // The confirmation callback must reflect what the backend actually
    // confirmed, not merely which radio option was selected.
    expect(onSaved).toHaveBeenCalledWith({ overrideCreated: true, email: 'sales@newmail.example' });
  });

  it('never reports an override as created when the backend did not confirm one', async () => {
    vi.mocked(api.recordContactResult).mockResolvedValue({ ok: true, event_id: 3, result: 'new_email_provided', override_created: false });
    setup();
    fireEvent.click(screen.getByLabelText('Уточнён новый email'));
    fireEvent.change(screen.getByPlaceholderText('new-contact@example.com'), { target: { value: 'sales@newmail.example' } });
    fireEvent.click(screen.getByRole('button', { name: 'Сохранить' }));
    await vi.waitFor(() => expect(api.recordContactResult).toHaveBeenCalledTimes(1));
    expect(onSaved).toHaveBeenCalledWith({ overrideCreated: false, email: null });
  });

  it('shows every required result option', () => {
    setup();
    for (const label of ['Не дозвонился', 'Контакт подтверждён', 'Уточнён новый email', 'Связаться позже', 'Поставщик не работает с запросом']) {
      expect(screen.getByLabelText(label)).toBeInTheDocument();
    }
  });
});
