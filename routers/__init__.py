"""Router package.

Intentionally empty: importing one router must not drag in every other one.
`webhook_app.py` imports only `routers.telegram`, and pulling
`routers.single_agent` in behind its back would force `python-multipart` into
the deployed image for an endpoint that app does not even serve.

The aggregate router for `main_client.py` lives in `routers/all.py`.
"""
