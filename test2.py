import gradio as gr
from gradio.components import Chatbot
from gradio import Blocks
from gradio import Interface
from dotenv import load_dotenv
from groq import Groq
import speech_recognition as sr 
import os
from gtts import gTTS
import time;

# Anika's API key
# GROQ_API_KEY= "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"
# os.environ["GROQ_API_KEY"] = GROQ_API_KEY
# api_key = os.getenv("GROQ_API_KEY")
# client = Groq(api_key=api_key)

load_dotenv()
API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=API_KEY)

def transcribe_audio(audio_path):
    recognizer = sr.Recognizer()
    with sr.AudioFile(audio_path) as source:
        # Read voice file
        audio = recognizer.record(source)
    try:
        # Google voice recognition
        text = recognizer.recognize_google(audio)
        return text
    except sr.UnknownValueError:
        return "Cannot read voice"
    except sr.RequestError:
        return "Not avaliable"

def process_input(history, message):
    if history is None:
        history = []

    user_text = ""
    files = message.get("files", [])  
    if files:
        for file in files:
            if file.endswith(".wav") or file.endswith(".mp3"):  
                transcribed_text = transcribe_audio(file)
                user_text = f"[🎤 Voice:]: {transcribed_text}"
                history.append((transcribed_text, ""))  
    
    if message.get("text"):  
        user_text = message["text"]
        history.append((user_text, ""))

    return history, gr.MultimodalTextbox(value=None, interactive=True)

def generate_plan(destination, interests, num_days, budget, time_period, num_people_slider, currency):
    prompt_parts = ["Generate a travel plan."]

    if destination.strip():
        prompt_parts.append(f"Destination: {destination}.")
    if interests.strip():
        prompt_parts.append(f"Interests: {interests}.")
    if num_days > 1:
        prompt_parts.append(f"Duration: {num_days} days.")
    if budget > 100:
        prompt_parts.append(f"Budget: {budget} {currency}.")
    if time_period and time_period.strip():
        prompt_parts.append(f"Time Period: {time_period}.")
    if num_people_slider > 1:
        prompt_parts.append(f"Number of People: {num_people_slider}.")

    # Final prompt ensuring at least a generic trip plan is generated
    user_prompt = " ".join(prompt_parts)

    messages = [
        {"role": "system", "content": "You are a holiday planner. Provide structured responses about attractions to visit, hotels to stay at, and restaurants to eat at on holiday. "},
        {"role": "user", "content": user_prompt}
    ]

    completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=messages,
        temperature=0.7,
        max_tokens=2048,
        top_p=0.9,
    )

    return completion.choices[0].message.content


def chat_with_bot_stream(user_input, audio, language, history):
    global conversation_history
    conversation_history, _ = process_input(history, user_input)

    # Language prompt
    language_prompt = f"Please respond in {language}."

    system_prompt = (
        "You are an expert travel guide for Japan with 10+ years of experience. "
        "You provide detailed vacation plans, suggest popular attractions, local food, and affordable luxury hotels. "
        "Your recommendations are practical and budget-friendly. "
        "You also speak 10+ languages and can respond in other languages if needed. " + language_prompt
    )

    # Generate with the context, history
    messages = [{"role": "system", "content": system_prompt}]
    for user_msg, ai_response in conversation_history[-3:]:  
        if user_msg:
            messages.append({"role": "user", "content": user_msg})
        if ai_response:
            messages.append({"role": "assistant", "content": ai_response})

    # Add the inputs
    user_input_text = conversation_history[-1][0]
    if conversation_history[-1][1] == "":
        messages.append({"role": "user", "content": user_input_text})

    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.7,
            max_completion_tokens=5000,
            top_p=0.9,
            stream=True
        )
    except Exception as e:
        return [("Tripper going offline, wait a second", "")]

    full_response = ""
    for chunk in completion:
        content = chunk.choices[0].delta.content or ""
        full_response += content  
        conversation_history[-1] = (conversation_history[-1][0], full_response)
        # Filter the history start with "system" (the first one)
        yield [(u, a) for u, a in conversation_history if u != "system"]
    
    if audio:
        try:
            #conversation_history.append("Generating text-to-speech...", "")
            #yield conversation_history

            audio_filename = f"bot_response_{int(time.time())}.mp3"
            tts = gTTS(full_response, lang="zh" if language == "中文" else "en")
            tts.save(audio_filename)

            # Insert the voice inside the chat
            conversation_history.append(("", (audio_filename,)))  
        except Exception as e:
            print(f"TTS failed: {e}")
    # Make sure see the voice inside the chat bar
    yield conversation_history 


#Title animation - https://www.gradio.app/guides/custom-CSS-and-JS
js_animate = """
function load_animate() {
  //Creat animation
  var text = " Welcome to Tripper, your personalized travel guide! ";

  // Remove existing animation to avoid duplication
  var existing = document.getElementById('gradio-animation');
  if (existing) existing.remove();

  // Create container
  var container = document.createElement('div');
  container.id = 'gradio-animation';
  container.style.fontSize = '2em';
  container.style.fontWeight = 'bold';
  container.style.textAlign = 'center';
  container.style.marginTop = '40px';

  var gradioContainer = document.querySelector('.gradio-container');
  gradioContainer.insertBefore(container, gradioContainer.firstChild);

  //Make Tripper a different color
  var specialWord = "Tripper";
  var specialColor = "#10FFCB";

  let delay = 0;

  for (let i = 0; i < text.length; i++) {
      let letter = document.createElement('span');
      letter.innerText = text[i];
      letter.style.opacity = '0';
      letter.style.transition = 'opacity 0.75s';

      if (text.substring(i, i + specialWord.length) === specialWord) {
          for (let j = 0; j < specialWord.length; j++) {
              let specialLetter = document.createElement('span');
              specialLetter.innerText = specialWord[j];
              specialLetter.style.opacity = '0';
              specialLetter.style.transition = 'opacity 0.75s';
              specialLetter.style.color = specialColor;

              container.appendChild(specialLetter);
              setTimeout(() => { specialLetter.style.opacity = '1'; }, delay * 100);
              delay++;
          }
          i += specialWord.length - 1;
      } else {
          container.appendChild(letter);
          setTimeout(() => { letter.style.opacity = '1'; }, delay * 100);
          delay++;
      }
  }

  //Set all components to dark mode
  document.querySelector(".gradio-container").classList.add("dark-mode");
  var span = document.querySelectorAll("span");
  var targetedSpans = Array.from(span).filter(function(span) {
      return span.innerText === "Enable Text-to-Speech";
  });
  targetedSpans.forEach(function(span) {
      span.classList.add("dark-mode");
  });
}

"""

#Dark-light theme changer
js_theme="""
function toggleTheme() {
    var theme = localStorage.getItem("theme");
    var isDarkMode = theme === "dark" || theme === null; //Default to dark mode

    var gradioContainer = document.querySelector(".gradio-container");
    var span = document.querySelectorAll("span");
    var targetedSpans = Array.from(span).filter(function(span) {
        return span.innerText === "Enable Text-to-Speech";
    });

    if (isDarkMode) {
        gradioContainer.classList.remove("dark-mode");
        gradioContainer.classList.add("light-mode");

        targetedSpans.forEach(function(span) {
            span.classList.remove("dark-mode");
            span.classList.add("light-mode");
        });
    } else {
        gradioContainer.classList.remove("light-mode");
        gradioContainer.classList.add("dark-mode");

        targetedSpans.forEach(function(span) {
            span.classList.remove("light-mode");
            span.classList.add("dark-mode");
        });
    }

    var themeButton = document.getElementById("theme-toggle-btn");
    themeButton.innerHTML = !isDarkMode ? "☼" : "☾";

    localStorage.setItem("theme", isDarkMode ? "light" : "dark");
}

"""

conversation_history = []
TITLE="""
<h1>✈️ Travel Assistant</h1>
<h3 class="subtitle">Discuss your travel plans and find out about your destination with our travel chatbot!</hh3>
"""

PLAN_TITLE="""
<h1>📅 Trip Planner</h1>
<h3 class="subtitle">Generate a day-to-day travel plan based on your preferences!<br>You can write out your plans in the "Trip Details"
section or enter your criteria with the other sliders and text boxes. The more details, the better!</h3>
"""

STYLE = """
<style>

  #send-button {
    width: 20%;
    self-align: end;
    margin-left: auto;
  }

  #theme-toggle-btn {
    width: 5%;
    self-align: end;
    margin-left: auto;
  }

  #checkbox {
    width: 5%;
    self-align: end;
    margin-left: auto;
  }

  #language-dropdown {
    width: 20%;
    self-align: end;
    margin-left: auto;
  }

  h1 { text-align:center; font-size: 24px; margin-bottom: 10px; }
  .subtitle { text-align:center; font-size: 18px; margin-bottom: 20px; }

  .light-mode, .dark-mode {
    transition: background-color 0.3s ease !important;
  }

  .light-mode {
    background-color: #ededed !important;
    color: #000000 !important;
  }
  .dark-mode {
    background-color: #0f0f11 !important;
    color: #ffffff !important;
  }

  .light-mode h1, .light-mode h3 {
    color: #000 !important;
  }
  .dark-mode h1, .dark-mode h3 {
    color: #ffffff !important;
  }

  .light-mode textarea, .light-mode .gradio-slider input, 
  .light-mode gradio-textbox, .light-mode #language-dropdown textarea {
    background-color: #ededed !important;
    color: #000 !important;
    border: 1px solid #444 !important;
  }
  .dark-mode textarea, .dark-mode .gradio-slider input, 
  .dark-mode gradio-textbox, .dark-mode #language-dropdown textarea {
    background-color: #27272a !important;
    color: #ffffff !important;
    border: 1px solid #444 !important;
  }

  .light-mode button {
    background-color: #d1d1d1 !important;
    color: #000 !important;
    border: 1px solid #ccc !important;
  }
  .dark-mode button {
    background-color: #282828 !important;
    color: #fff !important;
    border: 1px solid #444 !important;
  }

  .light-mode button:hover {
    background-color: #bbb !important;
    transition: background-color 0.3s ease !important;
  }
  .dark-mode button:hover {
    background-color: #151515 !important;
    transition: background-color 0.3s ease !important;
  }

  .light-mode .gr-markdown,
  .light-mode .gradio-container .gr-markdown {
      color: #000 !important;
  }
  .dark-mode .gr-markdown,
  .dark-mode .gradio-container .gr-markdown {
      color: #ffffff !important;
  }

</style>
"""

CURRENCY_MAP = {
  "USD": ("$", 100, 30000),
  "EUR": ("€", 100, 25000),
  "GBP": ("£", 100, 22000),
  "JPY": ("¥", 10000, 5000000),
  "INR": ("₹", 5000, 2000000),
  "AUD": ("A$", 100, 28000),
}

#Create custom theme colors
custom_theme = gr.themes.Default(primary_hue="teal", secondary_hue="teal")

#Update budget slider to chosen currency
def update_budget_slider(currency):
  symbol, min_val, max_val = CURRENCY_MAP[currency]
  return gr.update(label=f"Budget ({symbol}) (optional)", minimum=min_val, maximum=max_val)

with gr.Blocks(js=js_animate, theme=custom_theme) as demo:
    gr.HTML(STYLE)

    #Theme toggle button
    theme_toggle = gr.Button("☼", elem_id="theme-toggle-btn")
    theme_toggle.click(
        fn=lambda: None,
        inputs=[],
        outputs=[],
        js=js_theme
    )

    with gr.Tabs():

      with gr.TabItem("💬 Chat"):
        gr.HTML(TITLE)

        chatbot = gr.Chatbot(label="Travel Assistant Chatbot")

        # user_input = gr.Textbox(
        #     label="",
        #     placeholder="Enter your message here...",
        #     lines=1,
        # )
        
        user_input = gr.MultimodalTextbox(
            interactive=True,
            file_count="multiple",
            placeholder="Enter your message or upload talk to Tripper...",
            show_label=False,
            sources=["microphone"],
        )
        
        audio_button = gr.Checkbox(value=False, elem_id="checkbox", container=False, label="Enable Text-to-Speech")
        gr.Examples(examples=['What are some must-visit places in Japan during the Summer?',
                              'What are the best destinations for a budget-friendly trip in Europe?',
                              'Plan a four day trip to Scotland for a nature-loving family.'],
                    inputs=user_input, label="Examples")

        language_dropdown = gr.Dropdown(choices=["English", "Français", "Español", "Deutsch", "Italiano", "日本語", "中文"],
                                        value="English", label="Language", elem_id="language-dropdown", container=False)
        
        
        # send_button = gr.Button("Send", elem_id="send-button")
        
        # Process text + voice
        chat_msg = user_input.submit(
          fn=lambda:""
        ).then(
            fn=chat_with_bot_stream,
            inputs=[user_input, audio_button, language_dropdown, chatbot],
            outputs=chatbot,
            api_name="bot_response"
        ).then(
            fn=lambda _: "",
            inputs=None,
            outputs=user_input
        )


      #Trip planner section
      with gr.TabItem("🌍 Trip Planner"):
        gr.HTML(PLAN_TITLE)
        with gr.Row():
          with gr.Column():
            scenario_input = gr.Textbox(label="📝 Trip Details")
            destination_input = gr.Textbox(label="📍 Destination (optional)", placeholder="Enter your destination")
            interests_input = gr.Textbox(label="🎯 Interests (optional)", placeholder="E.g., hiking, food, museums")

          with gr.Column():
            num_days_slider = gr.Slider(minimum=1, maximum=30, step=1, value=None, label="📅 Number of Days (optional)", interactive=True)
            with gr.Row():
              #Dropdown to select currency for budget
              currency_dropdown = gr.Dropdown(
                choices=list(CURRENCY_MAP.keys()),
                value="USD",
                label="Select Currency",
                scale=2
              )
              budget_slider = gr.Slider(minimum=100, maximum=30000, step=100, value=None, label="💰 Budget ($) (optional)", interactive=True, scale=8)
              currency_dropdown.change(update_budget_slider, inputs=[currency_dropdown], outputs=[budget_slider])

            num_people_slider = gr.Slider(minimum=1, maximum=10, step=1, value=None, label="👨‍👩‍👧 Number of People (optional)", interactive=True)
            time_period = gr.Textbox(label="🕒 Time Period (optional)", placeholder="E.g., Summer, December, Christmas, 2025-07-10")

        generate_btn = gr.Button("Generate Plan", elem_id="send-button")
        plan_output = gr.Markdown(label="Plan")
        generate_btn.click(
          fn=lambda *args: "**Generating trip plan...**",
          inputs=[destination_input, interests_input, num_days_slider, budget_slider, time_period, num_people_slider, currency_dropdown],
          outputs=plan_output
        ).then(
            fn=generate_plan,
            inputs=[destination_input, interests_input, num_days_slider, budget_slider, time_period, num_people_slider, currency_dropdown],
            outputs=plan_output
        )

demo.launch(server_port=8080)
