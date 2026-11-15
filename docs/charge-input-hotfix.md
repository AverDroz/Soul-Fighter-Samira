# 0.3.2 — charged weapon input

The auto-release edge is now sent once per full charge cycle. Holding attack resumes native input after that edge; a six-frame retry is allowed only if no discharge was observed. QWER now has a charge progress bar in the companion HUD. Native laser duration is not overwritten.

Reviewed code only. Tests were explicitly not run at the user's request. Installation awaits game exit.

Installed after user closed Isaac; companion relaunched. No tests run.

Follow-up installed: charged A preserves RMB path; pending Q tracks current cursor; native linear beams retain corrected discharge angles across engine updates. No tests run at user request.
