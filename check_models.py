import google.generativeai as genai

genai.configure(api_key="AIzaSyCn-iekUFCW-zFQEPYM2Rn0aI4YQtVpzoQ")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)