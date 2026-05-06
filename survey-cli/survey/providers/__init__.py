"""Provider-specific survey patterns.

Each provider module exports:
  - detect(page_text): check if this provider is active
  - get_actions(snapshot, profile, provider): return NEMO-compatible actions
  - is_completed(page_text): check completion markers
"""
