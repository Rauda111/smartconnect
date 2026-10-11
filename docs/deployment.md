# Streamlit Community Cloud deployment

Deploy the controlled simulation prototype with these settings:

| Setting | Value |
| --- | --- |
| Repository | `Rauda111/smartconnect` |
| Branch | `main` |
| Main file path | `app.py` |
| Advanced settings → Python version | `3.13` |
| Secrets | Leave empty; none required |

Python 3.13 matches the locally tested prototype environment. This is separate
from the historical analysis environment recorded in the experiment manifest.
Keep the pinned `requirements.txt`; its packages resolve for Linux/Python 3.13.
No extra system packages, runtime file, or custom Streamlit configuration are
required. Choose Python in the Community Cloud deployment settings.

1. Sign in at <https://share.streamlit.io> with access to the GitHub repository.
2. Click **Create app**, choose the existing repository, and enter the settings above.
3. Choose an optional available app subdomain and deploy.
4. Run **Congested Wi-Fi / Video Call / Compare Both / seed 42** and inspect all
   five tabs. Ensure sharing is public and check the URL in a signed-out window.
5. Copy the resulting `https://….streamlit.app` URL into **Link to digital prototype**.

The app reads tracked `results/final_summary.csv` relative to `app.py`, independent
of the working directory. **Final Results** displays stored repeated-seed evidence;
the other tabs show the selected single-run simulation. Deployment must not
regenerate results. The 5G-like path is conceptual and simulated, not measurements
from a physical 5G network.

Local verification using the existing environment:

```sh
source venv/bin/activate
python -m unittest -v
python -m streamlit run app.py
```

Official deployment instructions:
<https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy>
