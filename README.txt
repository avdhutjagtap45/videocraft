# YouTube Asset Finder

Local Streamlit app: upload CSV, search Pexels/Pixabay, choose footage/images, download them with numbered filenames, and create one ZIP.

## Run
Windows:
`py -m venv .venv`
`.venv\\Scripts\\Activate.ps1`
`pip install -r requirements.txt`
`streamlit run app.py`

macOS/Linux:
`python3 -m venv .venv`
`source .venv/bin/activate`
`pip install -r requirements.txt`
`streamlit run app.py`

Get API keys from Pexels and Pixabay and paste them into the sidebar. CSV columns: No, Description, Type, Duration, Orientation.

Duration is informational in this version; the app does not trim clips. For rare historical scenes, search results may be weak.
