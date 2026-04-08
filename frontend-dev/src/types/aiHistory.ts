export type AIHistoryItemDTO = {
  id: number;
  created_at: string | null;
  actor_id: number | null;
  actor_name?: string | null;
  action: string;
  entity: string;
  entity_id?: string | null;
  diff_json?: Record<string, unknown> | null;
  request_id?: string | null;
};

export type AIHistoryResponseDTO = {
  items: AIHistoryItemDTO[];
  limit: number;
  offset: number;
  total: number;
};
