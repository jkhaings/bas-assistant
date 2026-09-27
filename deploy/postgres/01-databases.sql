-- Runs once, on a fresh volume.
-- LiteLLM keeps its virtual keys and spend logs in its own database.
CREATE DATABASE litellm;
-- make test-int migrates and uses this one, so test rows never reach the daily cap.
CREATE DATABASE bas_test;
