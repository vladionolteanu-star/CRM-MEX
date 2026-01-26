@echo off
echo Se verifica dependintele...
pip install -r requirements.txt
echo Se porneste aplicatia...
python -m streamlit run src/ui/app.py
pause
python -m streamlit run src/ui/app.py