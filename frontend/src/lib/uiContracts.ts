/**
 * UI-only contracts for the next Notes/AI iteration.
 * These types describe stable rendering inputs; they do not imply an API,
 * persistence model, provider integration or generated AI output.
 */

export type NoteKind = 'user_note' | 'text_annotation' | 'ai_suggestion';
export type NoteStatus = 'active' | 'resolved' | 'dismissed';

export interface NoteAnchor {
  messageId?: number;
  requestId?: number;
  supplierId?: number;
  quote?: string;
}

export interface NoteContract {
  id: string;
  kind: NoteKind;
  status: NoteStatus;
  authorName: string;
  body: string;
  createdAt: string;
  updatedAt?: string;
  anchor?: NoteAnchor;
}

export type AiQuickAction =
  | 'summarize_thread'
  | 'extract_offer_details'
  | 'draft_reply'
  | 'compare_supplier_terms';

export interface AiEntryPointContract {
  action: AiQuickAction;
  label: string;
  disabled?: boolean;
  reason?: string;
}

export interface EmailContextPanelContract {
  requestId?: number;
  supplierId?: number;
  notes?: NoteContract[];
  aiActions?: AiEntryPointContract[];
}
