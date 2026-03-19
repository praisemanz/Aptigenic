from flask import Flask, request, render_template
from openai import OpenAI, RateLimitError
from dotenv import load_dotenv
import os
import time

load_dotenv()

app = Flask(__name__)
client = OpenAI(api_key=os.environ.get('OPENAI_API_KEY'))

@app.route('/')
def welcome():
    return render_template('welcome.html')
@app.route('/chat')
def home():
    return render_template('index.html')

@app.route('/get', methods=['POST'])
def chatbot_response():
    user_input = request.form['msg']
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",  
            messages=[
                {"role": "system", "content": "You are a career coach assistant named Eeran."},
                {"role": "user", "content": user_input}
            ],
        )
        content = response.choices[0].message.content
        message = content.strip() if content else "No response received."
        return message
    except RateLimitError:
        time.sleep(1)  # Wait for 1 second before retrying 
        return "Rate limit exceeded. Please try again later."
    except Exception as e:
        return f"An error occurred: {str(e)}"

if __name__ == "__main__":
    app.run(debug=True)
