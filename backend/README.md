# Clinic API (Hindi voice agent backend)

Windows setup (PowerShell), inside the new `clinic-api` folder:

    python -m venv venv
    venv\Scripts\activate
    pip install -r requirements.txt
    pip install -r requirements-dev.txt   # only for tests
    python seed.py                        # creates clinic.db with FAKE data (resets everything!)
    uvicorn main:app --reload

Open http://127.0.0.1:8000/docs and click Authorize, then enter `dev-clinic-key`.
Change the key with the CLINIC_API_KEY environment variable.

Run tests:  python -m pytest -q