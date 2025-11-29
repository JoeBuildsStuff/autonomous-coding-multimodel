import os
import json
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

client = OpenAI(
    api_key=os.getenv("XAI_API_KEY"),
    base_url="https://api.x.ai/v1",
)

# Define functions that can be called by the model
def get_current_temperature(location: str, unit: str = "fahrenheit"):
    """Get the current temperature in a given location"""
    # Simulated temperature data
    temperature = 72 if unit == "fahrenheit" else 22
    return {
        "location": location,
        "temperature": temperature,
        "unit": unit,
    }

def calculate(operation: str, a: float, b: float):
    """Perform a basic mathematical calculation"""
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y if y != 0 else "Error: Division by zero",
    }
    
    if operation not in operations:
        return {"error": f"Unknown operation: {operation}"}
    
    result = operations[operation](a, b)
    return {
        "operation": operation,
        "a": a,
        "b": b,
        "result": result,
    }

# Create a mapping of function names to actual functions
tools_map = {
    "get_current_temperature": get_current_temperature,
    "calculate": calculate,
}

# Define the tool definitions for the API
tool_definitions = [
    {
        "type": "function",
        "function": {
            "name": "get_current_temperature",
            "description": "Get the current temperature in a given location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "The city and state, e.g. San Francisco, CA",
                    },
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "default": "fahrenheit",
                        "description": "Temperature unit",
                    },
                },
                "required": ["location"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate",
            "description": "Perform a basic mathematical calculation (add, subtract, multiply, divide)",
            "parameters": {
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["add", "subtract", "multiply", "divide"],
                        "description": "The mathematical operation to perform",
                    },
                    "a": {
                        "type": "number",
                        "description": "The first number",
                    },
                    "b": {
                        "type": "number",
                        "description": "The second number",
                    },
                },
                "required": ["operation", "a", "b"],
            },
        },
    },
]

def chat_with_function_calling(user_message: str):
    """Main function to handle chat with function calling"""
    messages = [{"role": "user", "content": user_message}]
    
    # Continue conversation until we get a final response
    max_iterations = 10
    iteration = 0
    
    while iteration < max_iterations:
        # Send request to the API
        response = client.chat.completions.create(
            model="grok-4-1-fast-reasoning",
            messages=messages,
            tools=tool_definitions,
            tool_choice="auto",
        )
        
        # Get the assistant's message
        assistant_message = response.choices[0].message
        messages.append(assistant_message)
        
        # Check if the model wants to call any functions
        if assistant_message.tool_calls:
            print(f"\n[Tool calls requested: {len(assistant_message.tool_calls)}]")
            
            # Process each tool call
            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)
                
                print(f"  Calling: {function_name}({function_args})")
                
                # Execute the function
                if function_name not in tools_map:
                    result = {"error": f"Function {function_name} not found"}
                else:
                    result = tools_map[function_name](**function_args)
                
                print(f"  Result: {result}")
                
                # Append the tool result to messages
                messages.append({
                    "role": "tool",
                    "content": json.dumps(result),
                    "tool_call_id": tool_call.id,
                })
        else:
            # No more tool calls, we have the final response
            return assistant_message.content
    
    return "Maximum iterations reached"

if __name__ == "__main__":
    # Example usage
    print("=== Function Calling Example ===\n")
    
    # Example 1: Temperature query
    print("Example 1: Temperature query")
    print("-" * 50)
    result = chat_with_function_calling("What's the temperature in San Francisco?")
    print(f"\nFinal response: {result}\n")
    
    # Example 2: Math calculation
    print("\nExample 2: Math calculation")
    print("-" * 50)
    result = chat_with_function_calling("What is 15 multiplied by 23?")
    print(f"\nFinal response: {result}\n")
    
    # Example 3: Combined query
    print("\nExample 3: Combined query")
    print("-" * 50)
    result = chat_with_function_calling(
        "What's the temperature in New York in celsius, and also calculate 100 divided by 4?"
    )
    print(f"\nFinal response: {result}\n")