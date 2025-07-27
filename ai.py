import os
import openai
import time
import random
from typing import Optional

# Handle imports for both package and direct execution
try:
    from . import tts
except ImportError:
    import tts


def _load_api_keys_from_secrets():
    """
    Load API keys from environment variables.

    Returns:
        str: alibaba_api_key or None if not found
    """
    # Get the key from environment variables
    api_key = os.environ.get("ALIBABA_API_KEY")
    if api_key:
        print("[INTERACTION] Using Alibaba API key from environment variable")
        return api_key

    print("[INTERACTION] ALIBABA_API_KEY environment variable not set")
    return None


def get_ai_response_with_retry(
    client, messages, model, max_retries=3, base_delay=1
) -> Optional[str]:
    """
    Get AI response with retry mechanism and exponential backoff.

    Args:
        client: OpenAI client instance
        messages: List of message dictionaries
        model: Model name to use
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff

    Returns:
        str: AI-generated response or None if all retries failed
    """
    for attempt in range(max_retries + 1):
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                timeout=30,  # 30 second timeout
                extra_body={"enable_thinking": False},
            )

            # Extract and return response
            response = completion.choices[0].message.content
            print(f"[AI] Received response from AI: {response[:100]}...")
            return response

        except openai.RateLimitError as e:
            if attempt < max_retries:
                delay = base_delay * (2**attempt) + random.uniform(0, 1)
                print(f"[AI] Rate limit error: {e}. Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
            else:
                print(f"[AI] Rate limit error: {e}. Max retries exceeded.")
                raise

        except openai.APIError as e:
            if attempt < max_retries:
                delay = base_delay * (2**attempt) + random.uniform(0, 1)
                print(f"[AI] API error: {e}. Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
            else:
                print(f"[AI] API error: {e}. Max retries exceeded.")
                raise

        except Exception as e:
            if attempt < max_retries:
                delay = base_delay * (2**attempt) + random.uniform(0, 1)
                print(f"[AI] Unexpected error: {e}. Retrying in {delay:.2f} seconds...")
                time.sleep(delay)
            else:
                print(f"[AI] Unexpected error: {e}. Max retries exceeded.")
                raise

    return None


def get_ai_response(question_text, language="EN", poi_data=None, current_poi_id=None):
    """
    Obtain AI-generated responses to visitor questions using Alibaba API.

    Args:
        question_text (str): The visitor's question
        language (str): The language to respond in ("EN" or "ZH")
        poi_data (dict): POI data to include in the system prompt
        current_poi_id (str): ID of the current POI where the robot is located

    Returns:
        str: AI-generated response
    """
    # Load API key from secrets.json
    api_key = _load_api_keys_from_secrets()

    if not api_key:
        print("[AI] No API key found")
        # Return appropriate message based on language
        if language == "ZH":
            return "抱歉，我现在无法访问知识库。请稍后再试。"
        else:
            return "I'm sorry, but I don't have access to the knowledge base right now. Please try again later."

    try:
        # Configure OpenAI client for Alibaba
        client = openai.OpenAI(
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            api_key=api_key,
        )
        model = "qwen3-32b"  # Alibaba's model

        # Create a system prompt with POI data
        system_prompt = f"""
        You are an expert museum guide robot with comprehensive knowledge of the exhibits.
        You work in a museum with exhibits and locations.
        
        You are an AI museum guide. Your personality is knowledgeable, polite, and concise.
        Your primary goal is to provide accurate information about the exhibits.
        
        Follow these rules:
        1. Give direct, factual answers in one or two simple sentences.
        2. Never tell jokes.
        3. If you don't have the answer to a question about the artifacts in the exhibits or sold items (and these ONLY), make up plausible information as this is a simulation.
        4. Write in plain text for a text-to-speech system.
        5. Respond in the language selected by the user: {language}
        6. Use only actual words, never letters or numbers alone.
        7. Convert ordinal numbers and symbols to words. For example, use "first to third" instead of "1st-3rd".
        8. Use only commas, periods, exclamation points and question marks as punctuation.
        9. When providing an answer, also include 3-4 follow-up questions that the user might want to ask next. Format your response as follows:
            [Your answer here]
            
            Follow-up questions:
            1. [First follow-up question]
            2. [Second follow-up question]
            3. [Third follow-up question]
            4. [Fourth follow-up question]
        """

        # Add information about current location if available
        if current_poi_id and poi_data and current_poi_id in poi_data:
            current_poi = poi_data[current_poi_id]
            # Handle both old format (dict) and new format (merged string)
            if isinstance(current_poi["name"], dict):
                current_poi_name = current_poi["name"].get(
                    "en" if language.upper() == "EN" else "zh", current_poi["name"]
                )
            else:
                # New merged format - extract from bilingual string
                name_parts = (
                    current_poi["name"].split(". ")
                    if "." in current_poi["name"]
                    else [current_poi["name"], ""]
                )
                current_poi_name = (
                    name_parts[0]
                    if language.upper() == "EN"
                    else (name_parts[1] if len(name_parts) > 1 else name_parts[0])
                )

            system_prompt += f"\n\nIMPORTANT: You are currently located at the {current_poi_name} exhibit. When answering questions about locations or navigation, consider this as your starting point."

        # Add POI information to the system prompt if available
        if poi_data:
            system_prompt += (
                "\n\nThe museum has the following exhibits and locations:\n"
            )
            for poi in poi_data.values():
                # Handle both old format (dict) and new format (merged string)
                if isinstance(poi["name"], dict):
                    name_en = poi["name"].get("en", poi["name"])
                    name_zh = poi["name"].get("zh", poi["name"])
                else:
                    # New merged format - extract from bilingual string
                    name_parts = (
                        poi["name"].split(". ")
                        if "." in poi["name"]
                        else [poi["name"], ""]
                    )
                    name_en = name_parts[0]
                    name_zh = name_parts[1] if len(name_parts) > 1 else name_parts[0]

                if isinstance(poi["description"], dict):
                    desc_en = poi["description"].get("en", poi["description"])
                    desc_zh = poi["description"].get("zh", poi["description"])
                else:
                    # New merged format - extract from bilingual string
                    desc_parts = (
                        poi["description"].split(". ")
                        if ". " in poi["description"]
                        else [poi["description"], ""]
                    )
                    desc_en = desc_parts[0] + (
                        "." if not desc_parts[0].endswith(".") else ""
                    )
                    desc_zh = (
                        ". ".join(desc_parts[1:])
                        if len(desc_parts) > 1
                        else desc_parts[0]
                    )

                if language.upper() == "ZH":
                    system_prompt += f"- {name_zh}: {desc_zh}\n"
                else:
                    system_prompt += f"- {name_en}: {desc_en}\n"

        # Construct user prompt
        user_prompt = f"Question: {question_text}"

        print(f"[AI] Processing question: {question_text}")

        # Make API call with retry mechanism
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        response = get_ai_response_with_retry(
            client=client,
            messages=messages,
            model=model,
            max_retries=3,
            base_delay=1,
        )

        # Handle response
        if response:
            print(f"[AI] Received response from AI: {response[:100]}...")
            return response
        else:
            # Return appropriate message based on language
            if language == "ZH":
                return "抱歉，我无法针对这个问题给出回答。"
            else:
                return "I'm sorry, I couldn't formulate a response to that question."

    except openai.APIError as e:
        print(f"[AI] OpenAI API error: {e}")
        # Return appropriate message based on language
        if language == "ZH":
            return "抱歉，我目前无法访问我的知识库。请稍后再试。"
        else:
            return "I'm sorry, I'm having trouble accessing my knowledge base right now. Please try again later."
    except Exception as e:
        print(f"[AI] Error getting AI response: {e}")
        # Return appropriate message based on language
        if language == "ZH":
            return "抱歉，在处理您的问题时遇到了意外错误。"
        else:
            return "I'm sorry, I encountered an unexpected error while processing your question."


def parse_ai_response(response_text):
    """
    Parse the AI response to extract the answer and follow-up questions.

    Args:
        response_text (str): The raw response from the AI

    Returns:
        dict: A dictionary containing 'answer' and 'follow_up_questions' keys
    """
    # Split the response into answer and follow-up questions
    if "Follow-up questions:" in response_text:
        parts = response_text.split("Follow-up questions:")
        answer = parts[0].strip()
        questions_text = parts[1].strip()

        # Extract follow-up questions
        follow_up_questions = []
        for line in questions_text.split("\n"):
            if line.strip() and (
                line.strip().startswith("1.")
                or line.strip().startswith("2.")
                or line.strip().startswith("3.")
                or line.strip().startswith("4.")
            ):
                question = line.split(".", 1)[1].strip()
                follow_up_questions.append(question)
    else:
        # If no follow-up questions format, treat entire response as answer
        answer = response_text
        follow_up_questions = []

    return {"answer": answer, "follow_up_questions": follow_up_questions}


def generate_tts_and_play(text_to_speak, language="EN", key=None):
    """
    Generate and play TTS audio for the given text.

    Args:
        text_to_speak (str): Text to convert to speech
        language (str): Language to use for TTS
        key (str): Optional key for the prompt

    Returns:
        str: Filename of the generated audio file
    """
    try:
        # Validate language
        language = language.upper()
        if language not in ["EN", "ZH"]:
            language = "EN"

        print(f"TTS: Generating audio for '{text_to_speak}' in {language}")
        tts.speak(text_to_speak, language, key=key)
        return "tts_output.wav"

    except Exception as e:
        print(f"TTS: Error generating/playing audio: {e}")
        return None
