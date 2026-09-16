import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { api } from '../../lib/api';
import { CommandPalette } from './CommandPalette';

/** The header search placeholder promises "заявки, поставщики, переписки,
 * текст письма" as searchable, but the palette never actually queried
 * suppliers -- a company findable only by ИНН (no request/thread name
 * match) was unfindable from global search. This guards the fix. */
vi.mock('../../lib/api', () => ({
  api: {
    listRequests: vi.fn(),
    listThreads: vi.fn(),
    listSupplierDirectory: vi.fn(),
    searchMessages: vi.fn(),
  },
}));

describe('CommandPalette', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listRequests).mockResolvedValue({ items: [] } as never);
    vi.mocked(api.listThreads).mockResolvedValue({ items: [] } as never);
    vi.mocked(api.searchMessages).mockResolvedValue({ items: [] } as never);
    vi.mocked(api.listSupplierDirectory).mockResolvedValue({
      items: [
        {
          id: 1, global_supplier_id: 1, supplier_id: 1, request_id: null,
          verification_status: 'verified', inn: '210500746448', name: 'ООО Ромашка',
          site: 'dompechei.ru', email: 'dompechei@yandex.ru', phone: null, note: '',
          categories: [], total_requests: 1, response_rate: 0, avg_response_hours: null,
        },
      ],
    } as never);
  });

  it('finds a supplier by bare ИНН digits even with no matching request/thread name', async () => {
    render(
      <MemoryRouter>
        <CommandPalette open onClose={vi.fn()} />
      </MemoryRouter>,
    );
    fireEvent.change(screen.getByPlaceholderText('Заявки, поставщики, переписки, текст письма…'), {
      target: { value: '210500746448' },
    });
    expect(await screen.findByText('ООО Ромашка')).toBeInTheDocument();
    expect(screen.getByText('ИНН 210500746448')).toBeInTheDocument();
  });
});
