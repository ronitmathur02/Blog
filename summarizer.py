import os
import config

def generate_summary(transcript):
    """Generate a summary of the meeting transcript or report that no audio was captured."""
    if not transcript or transcript.strip() == "":
        return "No audio could be captured from the meeting. Please check your audio settings or try a different approach."
        
    try:
        # Simple direct API call using requests
        import requests
        import json
        
        print("Using direct Groq API call...")
        
        # Basic headers with authorization
        headers = {
            "Authorization": f"Bearer {config.GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        
        # Request payload - note we're being clear about the source of the transcript
        payload = {
            "model": "llama3-8b-8192",
            "messages": [
                {
                    "role": "system",
                    "content": "You are a helpful assistant that generates concise meeting summaries."
                },
                {
                    "role": "user",
                    "content": f"Please summarize this meeting transcript into key points, action items, and decisions. If the transcript appears empty or inadequate, explain that the audio capture was unsuccessful: {transcript}"
                }
            ],
            "temperature": 0.5,
            "max_tokens": 500
        }
        
        # Make the API request
        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload
        )
        
        # Check if the request was successful
        if response.status_code == 200:
            result = response.json()
            if "choices" in result and len(result["choices"]) > 0:
                summary = result["choices"][0]["message"]["content"]
                return summary
            else:
                print(f"Unexpected response format: {response.text}")
                return f"Could not generate summary due to API error. The transcript contained {len(transcript)} characters."
        else:
            print(f"API request failed with status code {response.status_code}: {response.text}")
            return f"Error generating summary due to API error. The transcript contained {len(transcript)} characters."
            
    except Exception as e:
        print(f"Error in summary generation: {e}")
        return f"Error occurred during summary generation. The transcript contained {len(transcript)} characters."
