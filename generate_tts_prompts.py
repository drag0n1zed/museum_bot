#!/usr/bin/env python3
"""
Script to generate TTS prompts from raw POI data.
"""

import json
import os
import sys
import importlib.resources


def load_poi_data_from_package():
    """
    Load POI data from the file system.

    Returns:
        dict: POI data
    """
    try:
        # Try to find the data file in the file system
        # Get the directory of the current script
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Navigate to the data directory
        data_dir = os.path.join(os.path.dirname(current_dir), "data")
        data_file_path = os.path.join(data_dir, "raw_poi_data.json")

        # Check if the file exists
        if os.path.exists(data_file_path):
            with open(data_file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        else:
            print(f"Data file not found at: {data_file_path}")
            return None
    except Exception as e:
        print(f"Error loading POI data from file system: {e}")
        return None


def format_poi_name_for_tts(name_en, name_zh):
    """
    Format POI names for better TTS pronunciation.

    Args:
        name_en (str): English name
        name_zh (str): Chinese name

    Returns:
        tuple: Formatted English and Chinese names
    """
    # For English names, handle single letters to improve pronunciation
    # e.g., "Exhibition A" -> "Exhibition A" (keep as is)
    # This is a known limitation of TTS engines with single letters

    # For Chinese names, no special formatting needed
    return name_en, name_zh


def generate_poi_prompts(poi_data):
    """
    Generate TTS prompts for POIs.

    Args:
        poi_data (dict): POI data from JSON file

    Returns:
        dict: Generated TTS prompts
    """
    prompts = {}

    # Generate prompts for each POI
    for poi in poi_data.get("pois", []):
        poi_id = poi["id"]
        poi_name_en = (
            poi["name"]["en"] if isinstance(poi["name"], dict) else poi["name"]
        )
        poi_name_zh = (
            poi["name"]["zh"] if isinstance(poi["name"], dict) else poi["name"]
        )

        # Format names for better TTS
        poi_name_en, poi_name_zh = format_poi_name_for_tts(poi_name_en, poi_name_zh)

        # Arrival prompts - more natural phrasing without redundant descriptions
        prompts[f"arrival_{poi_id}"] = {
            "en": f"We've arrived at {poi_name_en}.",  # More natural phrasing
            "zh": f"我们已到达{poi_name_zh}！",  # More natural Chinese phrasing
        }

        # Navigation prompts - more natural
        prompts[f"navigate_{poi_id}"] = {
            "en": f"Let's go to {poi_name_en}.",
            "zh": f"我们去{poi_name_zh}吧！",  # Improved Chinese phrasing as requested
        }

    return prompts


def generate_system_prompts():
    """
    Generate system TTS prompts.

    Returns:
        dict: Generated system TTS prompts
    """
    prompts = {}

    # Tour complete prompt - more natural
    prompts["tour_complete"] = {
        "en": "I hope you've enjoyed your tour. Thank you for visiting!",
        "zh": "希望您喜欢这次参观，谢谢您的到来！",
    }

    # Error prompts - more natural phrasing
    prompts["error_no_knowledge_base_en"] = {
        "en": "I'm sorry, but I'm currently unable to access my knowledge base. Please try again later."
    }

    prompts["error_no_knowledge_base_zh"] = {
        "zh": "抱歉，我现在无法访问知识库，请稍后再试。"
    }

    prompts["error_could_not_formulate_en"] = {
        "en": "I'm sorry, I wasn't able to formulate a response to that question."
    }

    prompts["error_could_not_formulate_zh"] = {"zh": "抱歉，我无法回答这个问题。"}

    prompts["error_trouble_accessing_en"] = {
        "en": "I'm sorry, I'm having trouble accessing my knowledge base right now. Please try again in a moment."
    }

    prompts["error_trouble_accessing_zh"] = {
        "zh": "抱歉，我目前无法访问知识库，请稍后再试。"
    }

    prompts["error_unexpected_en"] = {
        "en": "I'm sorry, I encountered an unexpected error while processing your question. Please try again."
    }

    prompts["error_unexpected_zh"] = {
        "zh": "抱歉，处理您的问题时遇到了意外错误，请再试一次。"
    }

    # Language set prompts - more natural
    prompts["language_set_en"] = {"en": "The language has been set."}

    prompts["language_set_zh"] = {"zh": "语言设置完成。"}

    return prompts


def flatten_prompts(prompts):
    """
    Flatten the prompts dictionary to map keys to language-specific strings.

    Args:
        prompts (dict): Nested dictionary of prompts

    Returns:
        dict: Flattened dictionary of prompts
    """
    flattened = {}

    for key, value in prompts.items():
        if isinstance(value, dict):
            # If value is a dict, it contains language-specific prompts
            for lang, text in value.items():
                # If the key already ends with the language, don't add it again
                if key.endswith(f"_{lang}"):
                    flattened[key] = text
                else:
                    flattened[f"{key}_{lang}"] = text
        else:
            # If value is not a dict, use it directly
            flattened[key] = value

    return flattened


def save_prompts_to_package(prompts):
    """
    Save prompts to a JSON file in the package data directory using importlib.resources or file system.

    Args:
        prompts (dict): Dictionary of prompts

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Try package import first
        try:
            if hasattr(importlib.resources, "files"):
                # Python 3.9+
                data_dir = importlib.resources.files("museum_bot.data")
                output_path = data_dir.joinpath("generated_tts_prompts.json")

                # For Python 3.9+, we need to get the actual file path
                # Since we can't directly write with importlib.resources, we'll use the filesystem path
                output_file_path = str(output_path)
            else:
                # For Python 3.7-3.8, we'll assume a standard package structure
                import museum_bot.data

                data_dir = os.path.dirname(museum_bot.data.__file__)
                output_file_path = os.path.join(data_dir, "generated_tts_prompts.json")

            # Structure the output data
            output_data = {"tts_prompts": prompts}

            with open(output_file_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)

            print(f"Successfully saved {len(prompts)} prompts to {output_file_path}")
            return True
        except Exception as package_error:
            print(f"Error saving prompts to package: {package_error}")
            # Fall back to file system saving
            try:
                # Try to find the data directory in the file system
                # Get the directory of the current script
                current_dir = os.path.dirname(os.path.abspath(__file__))
                # Navigate to the data directory
                data_dir = os.path.join(os.path.dirname(current_dir), "data")
                output_file_path = os.path.join(data_dir, "generated_tts_prompts.json")

                # Structure the output data
                output_data = {"tts_prompts": prompts}

                with open(output_file_path, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=2)

                print(
                    f"Successfully saved {len(prompts)} prompts to {output_file_path}"
                )
                return True
            except Exception as fs_error:
                print(f"Error saving prompts to file system: {fs_error}")
                return False
    except Exception as e:
        print(f"Unexpected error saving prompts: {e}")
        return False


def main():
    """Main function to generate TTS prompts."""
    print("Generating TTS prompts...")

    # Load POI data from package
    poi_data = load_poi_data_from_package()
    if not poi_data:
        print("Failed to load POI data from package. Exiting.")
        return 1

    # Generate POI prompts
    poi_prompts = generate_poi_prompts(poi_data)
    print(f"Generated {len(poi_prompts)} POI prompt groups")

    # Generate system prompts
    system_prompts = generate_system_prompts()
    print(f"Generated {len(system_prompts)} system prompt groups")

    # Combine all prompts
    all_prompts = {**poi_prompts, **system_prompts}

    # Flatten prompts for output
    flattened_prompts = flatten_prompts(all_prompts)

    # Save prompts to package
    if save_prompts_to_package(flattened_prompts):
        print("TTS prompt generation complete.")
        return 0
    else:
        print("Failed to save TTS prompts. Exiting.")
        return 1


if __name__ == "__main__":
    exit(main())
