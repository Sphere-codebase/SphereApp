function buildChatPayload(message, activeSessionId, claimId) {
  const payload = { message };
  if (activeSessionId) {
    payload.session_id = activeSessionId;
  }
  if (claimId) {
    payload.claim_id = claimId;
  }
  return payload;
}
