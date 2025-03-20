# Tripper AI Chatbot
An AI chatbot capable of helping the user plan a trip. The focus of this project was incorporating accessibility, internationalization, user control, personalization, and visual feedback features to enhance user experience. We used Gradio to build the UI and Groq to implement the LLM.

The chatbot is also hosted on Hugging Face [here](https://huggingface.co/spaces/Ace895/Tripper_Travel_Planner_Assistant)!

## Running the application locally

1. Add a .env file to contain the Groq API key:

```
GROQ_API_KEY=your_api_key
```

2. Create a python environment
```
python -m venv gradio-env
```

3. Activate the python environment

For Linux/macOS: 
```
source gradio-env/bin/activate
```

For Windows: 
```
gradio-env\Scripts\activate
```

3. Install dependencies
```
pip install -r requirements.txt
```

4. Run the application

```
python app.py
```
