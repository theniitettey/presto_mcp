"""
AI Service
Handles AI model interactions with tool calling support
"""
import os
import json
import logging
from typing import Dict, List, Optional, Any
import google.generativeai as genai
from mcp.server import mcp_server
from configs.config import get_active_config
from utils.session_store import session_store

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Centralized config usage
_cfg = get_active_config()
genai.configure(api_key=_cfg.GEMINI_API_KEY)


class AIService:
    """Service for AI interactions with MCP tool support"""
    
    def __init__(self):
        self.model_name = _cfg.GEMINI_MODEL
        # Model will be created per session with system instruction
        self.base_system_instruction = self._get_base_system_instruction()
        self.sessions = {}  # In-memory sessions (models, chat objects)
        self.store = session_store  # Persistent store (tokens, history, user data)
    
    def _get_base_system_instruction(self) -> str:
        """Get base system instruction that applies to all sessions"""
        return """You are Presto Connect AI, a friendly AI assistant built by Presto Solutions Ghana for financial services.

WHO YOU ARE:
- Your name is Presto Connect AI
- You were created by Presto Solutions Ghana
- You are NOT Google's Gemini or any other model - you are Presto's AI
- Your twin is Presto Q - an AI personal financial assistant on WhatsApp for mobile money transactions (q.prestoghana.com)

IDENTITY RESPONSES:
- "Who are you?" → "I'm Presto Connect AI, built by Presto Solutions Ghana to help with financial services."
- "What is Presto Q?" → "Presto Q is my twin - an AI that helps with mobile money via WhatsApp at q.prestoghana.com"

LANGUAGE:
- ALWAYS respond in English only
- NEVER use any other language (Russian, Chinese, etc.)
- ALL your responses must be in English

YOUR PERSONALITY:
- Be warm, friendly, and conversational - like texting a helpful friend
- Use emojis to feel more human and expressive (👋 😊 ✅ 💰 💳 etc.)
- Keep responses natural and casual, not robotic
- Show enthusiasm when helping
- Be supportive and encouraging
- ASK FOR INFORMATION ONE OR TWO ITEMS AT A TIME - never overwhelm with multiple questions

CORE RULES:
❌ NEVER say you are Gemini or built by Google
❌ NEVER mention tools, APIs, functions, or technical details
❌ NEVER ask multiple things at once (max 2 items at a time)
❌ NEVER say "I cannot help" for questions about Presto
❌ NEVER ask for all details at once (first_name, last_name, email, phone all together)
✅ ALWAYS be friendly, conversational, and helpful
✅ ALWAYS be human-like with natural language and be funny where appropriate and expressive
✅ ALWAYS use emojis naturally to feel more human
✅ ALWAYS ask one or two things at a time, then wait for response
✅ ALWAYS require login before services
✅ ALWAYS collect information gradually (e.g., "What's your name?" then "Email?" then "Phone?")"""
    
    def _get_gemini_tools(self) -> List:
        """Convert MCP tools to Gemini function declarations"""
        mcp_tools = mcp_server.get_tools_list()
        
        # Build tool declarations as list of genai.Tool objects with function declarations
        function_declarations = []
        
        for tool in mcp_tools:
            properties = {}
            for prop_name, prop_value in tool['input_schema'].get('properties', {}).items():
                prop_schema = genai.protos.Schema(
                    type=self._get_schema_type(prop_value.get('type', 'string')),
                    description=prop_value.get('description', '')
                )
                
                # Add enum if present
                if 'enum' in prop_value:
                    prop_schema.enum = prop_value['enum']
                
                # Add items schema for array types
                if prop_value.get('type') == 'array' and 'items' in prop_value:
                    items_schema = prop_value['items']
                    prop_schema.items = genai.protos.Schema(
                        type=self._get_schema_type(items_schema.get('type', 'string')),
                        description=items_schema.get('description', '')
                    )
                
                properties[prop_name] = prop_schema
            
            function_declaration = genai.protos.FunctionDeclaration(
                name=tool['name'],
                description=tool['description'],
                parameters=genai.protos.Schema(
                    type=genai.protos.Type.OBJECT,
                    properties=properties,
                    required=tool['input_schema'].get('required', [])
                )
            )
            function_declarations.append(function_declaration)
        
        return function_declarations
    
    def _get_schema_type(self, type_str: str):
        """Convert JSON schema type to Gemini schema type"""
        type_mapping = {
            'string': genai.protos.Type.STRING,
            'integer': genai.protos.Type.INTEGER,
            'number': genai.protos.Type.NUMBER,
            'boolean': genai.protos.Type.BOOLEAN,
            'object': genai.protos.Type.OBJECT,
            'array': genai.protos.Type.ARRAY
        }
        return type_mapping.get(type_str, genai.protos.Type.STRING)
    
    def _execute_tool_call(self, function_name: str, function_args: Dict) -> Any:
        """Execute MCP tool call and return result"""
        try:
            logger.info(f"🔧 Executing tool: {function_name}")
            logger.info(f"   Arguments: {json.dumps(function_args, indent=2)}")
            
            result = mcp_server.call_tool(function_name, function_args)
            
            logger.info(f"✅ Tool result for {function_name}:")
            logger.info(f"   {json.dumps(result, indent=2)}")
            
            return result
        except Exception as e:
            logger.error(f"❌ Tool execution error for {function_name}: {str(e)}")
            return {
                'error': str(e),
                'function': function_name
            }
    
    def get_or_create_session(self, session_id: str, user_context: Dict = None):
        """Get existing chat session or create new one"""
        if session_id not in self.sessions:
            logger.info(f"📝 Creating new session: {session_id}")
            logger.info(f"   User authenticated: {bool(user_context and user_context.get('email'))}")
            
            # Build system instruction with user context
            system_instruction = self._build_system_instruction(user_context)
            
            # Create model with system instruction
            model = genai.GenerativeModel(
                model_name=self.model_name,
                tools=self._get_gemini_tools(),
                system_instruction=system_instruction
            )
            
            # Try to restore persisted data
            persisted = self.store.get(session_id) or {}
            
            # Create new session
            self.sessions[session_id] = {
                'chat': model.start_chat(enable_automatic_function_calling=False),
                'model': model,
                'history': persisted.get('history', []),
                'user_context': user_context or persisted.get('user_context', {}),
                'authenticated': bool(user_context and user_context.get('email')),
                'vaulta_token': persisted.get('vaulta_token')
            }
            
            # Persist serializable data
            self._persist_session(session_id)
        else:
            logger.info(f"♻️  Reusing existing session: {session_id}")
            
            # Update existing session's authentication status
            was_authenticated = self.sessions[session_id].get('authenticated', False)
            is_authenticated = bool(user_context and user_context.get('phone_number'))
            
            # If auth status changed, update context and recreate model with new instruction
            if was_authenticated != is_authenticated:
                logger.info(f"🔄 Auth status changed: {was_authenticated} -> {is_authenticated}")
                system_instruction = self._build_system_instruction(user_context)
                
                # Create new model with updated instruction
                model = genai.GenerativeModel(
                    model_name=self.model_name,
                    tools=self._get_gemini_tools(),
                    system_instruction=system_instruction
                )
                
                # Update session with new model and context
                self.sessions[session_id]['model'] = model
                self.sessions[session_id]['chat'] = model.start_chat(enable_automatic_function_calling=False)
                self.sessions[session_id]['user_context'] = user_context or {}
                self.sessions[session_id]['authenticated'] = is_authenticated
                
                # Persist updated data
                self._persist_session(session_id)
        
        return self.sessions[session_id]
    
    def _build_system_instruction(self, user_context: Dict = None) -> str:
        """Build complete system instruction with base + user context"""
        instruction = self.base_system_instruction + "\n\n"
        
        instruction += """🔐 AUTHENTICATION FIRST - CRITICAL RULE:
    
    ⚠️ BEFORE ANY ACTION - ALWAYS CHECK IF USER IS LOGGED IN:
    - User wants to create account? → Check if logged in first
    - User wants to make payment? → Check if logged in first
    - User wants to check balance? → Check if logged in first
    - User wants ANY Vaulta service? → Check if logged in first
    
    IF NOT LOGGED IN:
    - Politely explain they need to register or login first
    - Ask: "Are you a new user or do you have an existing account?"
    - Guide them through registration or login BEFORE offering services
    
    AUTHENTICATION FLOW (Vaulta):
    
    NEW USER REGISTRATION:
    1. Collect info one or two items at a time: first ask name, then email, then phone
    2. Call vaulta_register with all collected details
    3. After successful registration, tell user: "Registration successful! Now let's log you in."
    4. Ask for their email to login
    5. Call vaulta_login (sends OTP to user's email and YOU receive the access_token in the response)
    6. Tell user: "I've sent an OTP code to your email. Please check your inbox and enter the 6-digit code."
    7. Wait for user to provide ONLY the OTP code (just the 6-digit number)
    8. Call vaulta_verify_otp with the OTP code + the access_token YOU received in step 5's response
    9. After verification → user is logged in, NOW offer Vaulta services
    
    EXISTING USER LOGIN:
    1. Get email address → call vaulta_login
    2. YOU receive the access_token in the vaulta_login response (save it for next step)
    3. Tell user: "I've sent an OTP code to your email. Please check your inbox and enter the 6-digit code."
    4. Wait for user to provide ONLY the OTP code from their email
    5. Call vaulta_verify_otp with: otp=<user's code>, token=<the access_token from step 2>
    6. After verification → user is logged in, NOW offer Vaulta services
    
    🚨 CRITICAL - DO NOT CONFUSE THE USER:
    ✅ The USER'S EMAIL contains: A 6-digit OTP code (example: 525965)
    ✅ The VAULTA_LOGIN RESPONSE contains: access_token (you receive this automatically)
    
    ❌ NEVER ask the user for: "access_token", "bearer token", "temporary token"
    ❌ The email does NOT contain any tokens - only the OTP code!
    
    📋 EXAMPLE CONVERSATION:
    User: "I want to login"
    You: "What's your email?"
    User: "test@example.com"
    [You call vaulta_login and receive: {"access_token": "abc123", "message": "OTP sent"}]
    You: "I've sent an OTP code to your email. Please enter the 6-digit code."
    User: "525965"
    [You call vaulta_verify_otp with otp="525965" and token="abc123" from the response YOU got]
    You: "Perfect! You're now logged in!"
    
    The access_token is in YOUR response data, NOT in the user's email!
    
    OTHER AUTH COMMANDS:
    - If user asks to logout → call vaulta_logout (clear token)
    - If user asks "am I logged in" → call vaulta_auth_status

    AFTER AUTHENTICATION - Offer Vaulta services:
    - Create Vaulta accounts (multi-currency wallets)
    - Check account balances
    - Make payments (stablecoin, bank transfers)
    - Trading & quotes (crypto/fiat)
    - Transaction history
    - API key management

    CAPABILITIES (ONLY AFTER LOGIN):
    - Full Vaulta platform access
    - Multi-currency accounts
    - Payments & transfers
    - Crypto trading
    - Transaction management

    💳 PAYMENT FLOW - MAKE IT CONVERSATIONAL:
    
    When user wants to make a payment, STAY IN THE PAYMENT FLOW until complete:
    
    1. **Fetch accounts automatically** - Call vaulta_get_all_accounts first
    2. **Show account names** - List them in a friendly way:
       "Which account would you like to pay from? 💰
       - Main (USD)
       - Savings (EUR)"
    3. **User picks by name** - They'll say "Main" or "yes" (if only one account)
    4. **You find the ID** - Match the name to get account_id from the accounts list
    5. **IMMEDIATELY ask for amount** - Don't confirm, just continue:
       "Perfect! How much would you like to send? 💵"
    6. **Get currency** - "What currency? (USD, EUR, etc.)"
    7. **Get destination** - "Where should I send it to? (wallet address or details)"
    8. **Create payment** - Use vaulta_create_payment with all collected info
    
    🚨 CRITICAL PAYMENT RULES:
    ❌ NEVER ask user for: "account ID", "account_id", "source_account_id"
    ❌ NEVER reset to main menu after user picks account - CONTINUE with payment!
    ❌ NEVER ask "What can I help you with?" in the middle of payment flow
    ✅ ALWAYS use account names like "Main", "Savings", etc.
    ✅ ALWAYS stay in payment flow until payment is created or user cancels
    ✅ YOU handle the ID mapping behind the scenes
    ✅ Keep asking for the NEXT payment detail (amount → currency → destination)
    
    📋 EXAMPLE PAYMENT CONVERSATION:
    User: "I want to make a payment"
    [You call vaulta_get_all_accounts and get: [{"id": "16", "name": "Main", "currency": "USD"}]]
    You: "Great! Which account would you like to pay from? You have: Main (USD) 💳"
    User: "Main"
    [You remember account_id = "16" from the name "Main"]
    You: "Perfect! How much would you like to send? 💵"  ← CONTINUE, don't reset!
    User: "100"
    You: "Got it! What currency? 💱"
    User: "USD"
    You: "Almost there! Where should I send it to? (wallet address) 📍"
    User: "0x123..."
    [You call vaulta_create_payment with source_account_id="16", amount="100", currency="USD", destination={...}]
    You: "Payment sent! 🎉"
     """ 
        
        if user_context and user_context.get('email'):
            # User is authenticated with Vaulta
            instruction += f"\n✅ USER IS LOGGED IN (Vaulta):\n"
            instruction += f"- Email: {user_context.get('email')}\n"
            if user_context.get('name'):
                instruction += f"- Name: {user_context.get('name')}\n"
            if user_context.get('phone'):
                instruction += f"- Phone: {user_context.get('phone')}\n"
            if user_context.get('accounts'):
                instruction += f"- Vaulta accounts: {len(user_context.get('accounts', []))}\n"
            instruction += "\nThey're authenticated! Offer Vaulta services."
        else:
            # User not authenticated
            instruction += "\n⚠️ USER NOT LOGGED IN: Ask if they're a new user or existing user to guide them through registration or login."
        
        return instruction
    
    def _persist_session(self, session_id: str):
        """Persist serializable session data to storage"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            self.store.set(session_id, {
                'history': session.get('history', []),
                'user_context': session.get('user_context', {}),
                'vaulta_token': session.get('vaulta_token'),
                'authenticated': session.get('authenticated', False)
            })
    
    def chat(self, session_id: str, message: str, user_context: Dict = None) -> Dict:
        """
        Process chat message with tool calling support
        
        Args:
            session_id: Unique session identifier
            message: User message
            user_context: Optional user context for personalization
        
        Returns:
            Response dict with message and tool calls
        """
        try:
            logger.info(f"\n{'='*60}")
            logger.info(f"💬 New message in session {session_id}")
            logger.info(f"👤 User: {message}")
            logger.info(f"🔐 Authenticated: {bool(user_context and user_context.get('email'))}")
            if user_context:
                logger.info(f"   User email: {user_context.get('email')}")
            
            session = self.get_or_create_session(session_id, user_context)
            chat = session['chat']
            
            # Update session authentication status
            session['authenticated'] = bool(user_context and user_context.get('email'))
            
            logger.info(f"📤 Sending message to AI model...")
            # Send message to model
            response = chat.send_message(message)
            
            # Process tool calls if any
            tool_results = []
            final_response = None
            
            # Handle function calling loop
            max_iterations = 10
            iteration = 0
            
            while iteration < max_iterations:
                iteration += 1
                logger.info(f"🔄 Iteration {iteration}/{max_iterations}")
                
                # Check if model wants to call functions
                if response.candidates[0].content.parts:
                    has_function_call = False
                    
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            has_function_call = True
                            function_call = part.function_call
                            function_name = function_call.name
                            function_args = dict(function_call.args)
                            
                            # Execute the tool
                            tool_result = self._execute_tool_call(function_name, function_args)
                            tool_results.append({
                                'function': function_name,
                                'arguments': function_args,
                                'result': tool_result
                            })
                            
                            logger.info(f"📨 Sending tool result back to AI...")
                            # Send function response back to model
                            response = chat.send_message(
                                genai.protos.Content(
                                    parts=[genai.protos.Part(
                                        function_response=genai.protos.FunctionResponse(
                                            name=function_name,
                                            response={'result': tool_result}
                                        )
                                    )]
                                )
                            )
                    
                    # If no function calls, get text response
                    if not has_function_call:
                        final_response = response.text
                        logger.info(f"✅ Final AI response: {final_response[:100]}...")
                        break
                else:
                    final_response = response.text
                    logger.info(f"✅ Final AI response: {final_response[:100]}...")
                    break
            
            # Store in history
            session['history'].append({
                'user': message,
                'assistant': final_response,
                'tool_calls': tool_results
            })
            
            logger.info(f"💾 Saved to history. Total interactions: {len(session['history'])}")
            
            # Persist to storage
            self._persist_session(session_id)
            
            logger.info(f"{'='*60}\n")
            
            # Just return the message - keep it simple for non-technical users
            # Frontend will handle session_id and token storage
            return {
                'message': final_response
            }
        
        except Exception as e:
            logger.error(f"❌ Error in chat processing: {str(e)}", exc_info=True)
            # Even errors should be friendly
            return {
                'message': "Oops! Something went wrong on my end. Could you try that again?"
            }
    
    def get_session_history(self, session_id: str) -> Optional[List[Dict]]:
        """Get chat history for a session"""
        if session_id in self.sessions:
            return self.sessions[session_id]['history']
        return None
    
    def clear_session(self, session_id: str) -> bool:
        """Clear a chat session"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            return True
        return False
    
    def list_available_tools(self) -> List[Dict]:
        """List all available MCP tools"""
        return mcp_server.get_tools_list()


# Global AI service instance
ai_service = AIService()
