import gradio as gr
from dotenv import load_dotenv
from groq import Groq
import speech_recognition as sr 
import os
from gtts import gTTS
import time;
import folium
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

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

def generate_plan(details, destination, interests, num_days, budget, time_period, num_people_slider, currency, language):
    
    #Check if an adequate number of fields were field
    if not any([destination, details]):
        return "", "", "**❌ Please fill either Destination or Trip Details so we know where you are planning to travel.**"
    
    prompt_parts = ["Generate a travel plan."]

    if details.strip():
        prompt_parts.append(f"Details: {details}. ")
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
    prompt_parts.append(f"Please respond in {language}.")

    # Final prompt ensuring at least a generic trip plan is generated
    user_prompt = " ".join(prompt_parts)

    messages = [
        {"role": "system", "content": "You are a holiday planner. Provide structured responses about attractions to visit, hotels to stay at, and restaurants to eat at on holiday. You can respond in many languages when prompted."},
        {"role": "user", "content": user_prompt}
    ]

    completion = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=messages,
        temperature=0.7,
        max_tokens=2048,
        top_p=0.9,
    )

    trip_text = completion.choices[0].message.content
    places = extract_places(trip_text)

    return trip_text, places, ""


def chat_with_bot_stream(user_input, audio, language, history):
    if history is None:
        history = []
    history, _ = process_input(history, user_input)


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
    for user_msg, ai_response in history[-3:]:  
        if user_msg:
            messages.append({"role": "user", "content": user_msg})
        if ai_response:
            if isinstance(ai_response, tuple):
                messages.append({"role": "assistant", "content": ai_response[0]})
            else:
                messages.append({"role": "assistant", "content": ai_response})

    # Add the inputs
    if history[-1][1] == "":
        messages.append({"role": "user", "content": history[-1][0]})

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
        history[-1] = (history[-1][0], full_response)
        # Filter the history start with "system" (the first one)
        yield [(u, a) for u, a in history if u != "system"]
    
    if audio:
        try:
            history.append(("", "🔊Generating text-to-speech..."))
            yield history

            #Get chosen language 
            language_map = {
                "English": "en",
                "Français": "fr",
                "Español": "es",
                "Deutsch": "de",
                "Italiano": "it",
                "日本語": "ja",
                "中文": "zh"
            }
            tts_language = language_map.get(language, "en") #Defaults to english

            audio_filename = f"bot_response_{int(time.time())}.mp3"
            tts = gTTS(full_response, lang=tts_language)
            tts.save(audio_filename)

            # Insert the voice inside the chat
            history.append(("", (audio_filename,)))  
        except Exception as e:
            print(f"TTS failed: {e}")
    # Make sure see the voice inside the chat bar
    yield history 

# Geocode function using Geopy
def geocode_location(location_name):
    geolocator = Nominatim(user_agent="trip-planner")  # Use your custom user agent
    location = geolocator.geocode(location_name)
    if location:
        return [location.latitude, location.longitude], location_name  
    else:
        return None

def generate_map(locations):
    # Split the string of locations into a list
    location_list = locations.strip().split("\n")
    
    # Convert location names into latitudes and longitudes 
    coordinates = []
    for location in location_list:
        coord = geocode_location(location)
        if coord:
          coordinates.append(coord)
    
    # Check if any coordinates were found
    if len(coordinates) >= 2:

        #Filter out locations that are too far apart from the reference coordinate
        filtered_coordinates = [coordinates[0]]
        for coord in coordinates[1:]:
            distance = geodesic(coordinates[0][0], coord[0]).km
            if distance <= 500:
                filtered_coordinates.append(coord)

        if filtered_coordinates:
            m = folium.Map(location=filtered_coordinates[0][0], zoom_start=12)

            for coord, name in filtered_coordinates[1:]:
                folium.Marker(
                    location=coord,
                    tooltip=name  # Tooltip appears on hover
                ).add_to(m)

            return m._repr_html_()

#Extract names of places in trip plan
def extract_places(trip_text):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
              {"role": "system", "content": "Extract the names of places (museums, hotels, restaurants, attractions) from this itinerary. Just print the names, no other formatting or words. Put the name of the destination (city) on the first line."},
              {"role": "user", "content": trip_text}
          ],
        temperature=0,
        max_completion_tokens=5000,
        top_p=1
    )

    return response.choices[0].message.content.strip()

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
  container.style.fontSize = '32pt';
  container.style.fontWeight = 'bold';
  container.style.textAlign = 'center';

  var gradioContainer = document.querySelector('.gradio-container');
  gradioContainer.insertBefore(container, gradioContainer.firstChild);

  //Make Tripper a different color
  var specialWord = "Tripper";
  var specialColor = "#91CFE5";

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

  #gradio-animation {
    height: 150px;
    background-image: url(https://cdn-icons-png.flaticon.com/512/422/422914.png);
    background-repeat: no-repeat;
    background-size: 150px 150px;
    margin: 40px 0 0 80px;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: center;
    white-space: pre;
  }

  #send-button {
    width: 20%;
    align-self: end;
    margin-left: auto;
  }

  #theme-toggle-btn {
    min-width: 5%;
    align-self: end;
    margin-left: auto;
  }

  #language-container {
    display: flex'
    justify-content: flex-start;
    width: 20%;
    align-items: flex-end;
    align-self: end;
  }

  #language-dropdown {
    width: 20%;
    position: relative;
    margin: 0;
  }

  #checkbox {
    width: 5%;
    align-self: end;
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

  .light-mode h1, .light-mode h3, .light-mode p, 
  .light-mode li, .light-mode strong, .light-mode .svelte-i3tvor,
  .light-mode .svelte-p5q82i {
    color: #000 !important;
  }
  .dark-mode h1, .dark-mode h3, .dark-mode p, 
  .dark-mode li, .dark-mode strong, .dark-mode .svelte-i3tvor,
  .dark-mode .svelte-p5q82i {
    color: #ffffff !important;
  }

  .light-mode .bubble-wrap, 
  .light-mode .multimodal-textbox, .light-mode .svelte-i3tvor {
    background-color: #ffffff !important;
  }
  .dark-mode .bubble-wrap, 
  .dark-mode .multimodal-textbox, .dark-mode .svelte-i3tvor  {
    background-color: #201c1c !important;
  }

   .light-mode .bot, .light-mode .message, .light-mode .placeholder-content,
   .light-mode .progress-text {
    background-color:rgb(245, 245, 245) !important;
    border-color: rgb(185, 182, 182) !important;
   }

   .dark-mode .bot, .dark-mode .message, .dark-mode .placeholder-content,
   .dark-mode .progress-text {
    background-color: #27272a !important;
    border-color: #3f3f46 !important;
   }

  .light-mode textarea, .light-mode .gradio-slider input, 
  .light-mode gradio-textbox {
    background-color: #ededed !important;
    color: #000 !important;
    border: 1px solid rgb(185, 182, 182) !important;
  }
  .dark-mode textarea, .dark-mode .gradio-slider input, 
  .dark-mode gradio-textbox {
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

  .light-mode .svelte-y6qw75 {
    background-color: #d1d1d1 !important;
    color: #000 !important;
  }

  .dark-mode .svelte-1hfxrpf, .dark-mode .svelte-y6qw75 {
    background-color: #282828 !important;
    color: #fff !important;
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
custom_theme = gr.themes.Default(primary_hue="blue", secondary_hue="blue")

#Update budget slider to chosen currency
def update_budget_slider(currency):
  symbol, min_val, max_val = CURRENCY_MAP[currency]
  return gr.update(label=f"Budget ({symbol}) (optional)", minimum=min_val, maximum=max_val)

with gr.Blocks(js=js_animate, theme=custom_theme) as demo:
    gr.HTML(STYLE)

    with gr.Row(elem_id="language-container"):
        language_dropdown = gr.Dropdown(choices=[
            "🇬🇧 English", 
            "🇫🇷 Français", 
            "🇪🇸 Español", 
            "🇩🇪 Deutsch", 
            "🇮🇹 Italiano", 
            "🇯🇵 日本語", 
            "🇨🇳 中文"
        ], value="🇬🇧 English", label="Language", elem_id="language-dropdown", container=False, scale=8)

        #Theme toggle button
        theme_toggle = gr.Button("☼", elem_id="theme-toggle-btn", scale=2)
        theme_toggle.click(
            fn=lambda: None,
            inputs=[],
            outputs=[],
            js=js_theme
        )

    with gr.Tabs():

      with gr.TabItem("💬 Chat"):
        gr.HTML(TITLE)

        chatbot = gr.Chatbot(label="Travel Assistant Chatbot", elem_id="chatbot")
        
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
                
        # Process text + voice
        chat_msg = user_input.submit(
            fn=lambda _: gr.update(interactive=False, submit_btn=False),  
            inputs=[],
            outputs=user_input
        ).then(
            fn=chat_with_bot_stream,
            inputs=[user_input, audio_button, language_dropdown, chatbot],
            outputs=chatbot,
            api_name="bot_response"
        ).then(
            fn=lambda _: "",
            inputs=None,
            outputs=user_input
        ).then(
            fn=lambda _: gr.update(interactive=True, submit_btn=True),  
            inputs=[],
            outputs=user_input
        )


      #Trip planner section
      with gr.TabItem("🌍 Trip Planner"):
        gr.HTML(PLAN_TITLE)
        with gr.Row():
          with gr.Column():
            details_input = gr.Textbox(label="📝 Trip Details")
            destination_input = gr.Textbox(label="📍 Destination (optional)", placeholder="Enter your destination")
            interests_input = gr.Textbox(label="🎯 Interests (optional)", placeholder="E.g., hiking, food, museums")

          with gr.Column():
            num_days_slider = gr.Slider(minimum=1, maximum=30, step=1, value=None, label="📅 Number of Days (optional)", interactive=True)
            with gr.Row():
              #Dropdown to select currency for budget
              currency_dropdown = gr.Dropdown(
                choices=list(CURRENCY_MAP.keys()),
                value="USD",
                show_label=False,
                scale=2
              )
              budget_slider = gr.Slider(minimum=100, maximum=30000, step=100, value=None, label="💰 Budget ($) (optional)", interactive=True, scale=8)
              currency_dropdown.change(update_budget_slider, inputs=[currency_dropdown], outputs=[budget_slider])

            num_people_slider = gr.Slider(minimum=1, maximum=10, step=1, value=None, label="👨‍👩‍👧 Number of People (optional)", interactive=True)
            time_period = gr.Textbox(label="🕒 Time Period (optional)", placeholder="E.g., Summer, December, Christmas, 2025-07-10")

        generate_btn = gr.Button("Generate Plan", elem_id="send-button")
        clear_plan = gr.Button("Reset", elem_id="send-button")

        error_output = gr.Markdown()
        plan_output = gr.Markdown(label="Plan")
        map_output = gr.HTML("")
        places = gr.Textbox(visible=False)

        generate_btn.click(
            fn=lambda *args: ("**Generating trip plan...**", "", ""),  
            inputs=[],
            outputs=[plan_output, map_output, error_output]
        ).then(
            fn=generate_plan,
            inputs=[details_input, destination_input, interests_input, num_days_slider, budget_slider, time_period, num_people_slider, currency_dropdown, language_dropdown],
            outputs=[plan_output, places, error_output]  
        ).then(
            fn=lambda *args: ("Generating map..."),  
            inputs=[],
            outputs=map_output
        ).then(
            fn=generate_map,
            inputs=places,  
            outputs=map_output
        )

        clear_plan.click(
            fn=lambda: ("", "", "", None, None, "", None, "USD", "", "", ""),
            inputs=[],
            outputs=[
                details_input,
                destination_input,
                interests_input,
                num_days_slider,
                budget_slider,
                time_period,
                num_people_slider,
                currency_dropdown,
                plan_output,
                map_output,
                error_output
            ]
        ).then(
            fn=update_budget_slider,
            inputs=[currency_dropdown],  
            outputs=[budget_slider]
        ).then(
            fn=lambda: (None),
            inputs=[],
            outputs=[budget_slider]
        )

demo.launch()