from flask import Blueprint, request, jsonify
from services.ai import ai_service
from configs.status import determine_status
from mcp.vaulta import vaulta_mcp
import uuid

chat_bp = Blueprint('chat', __name__)


@chat_bp.route('/chat', methods=['POST'])
def chat():
    """
    Chat endpoint with AI and MCP tool calling support
    
    Request body:
        - message: User message (required)
        - session_id: Chat session ID (optional, will be generated if not provided)
        - token: JWT auth token (optional, for user context)
    
    Response (first time):
        - message: AI response text
        - session_id: Session identifier
        - token: Auth token (or null)
        - status: Conversation status
    
    Response (subsequent):
        - message: AI response text
        - status: Current conversation status
    """
    try:
        data = request.get_json()
        
        if not data or not data.get('message'):
            return jsonify({
                'message': 'Could you please send me a message? 😊',
                'status': 'error'
            }), 400
        
        message = data.get('message')
        session_id = data.get('session_id')
        is_first_message = not session_id
        session_id = session_id or str(uuid.uuid4())
        vaulta_token = data.get('token')
        
        # Try to get token from AI session if not provided by frontend
        if not vaulta_token:
            ai_session = ai_service.sessions.get(session_id)
            if ai_session:
                vaulta_token = ai_session.get('vaulta_token')
                if vaulta_token:
                    print(f"🔑 Retrieved token from in-memory session: {vaulta_token[:20]}...")
            
            # Also check persistent store
            if not vaulta_token:
                persisted = ai_service.store.get(session_id)
                if persisted:
                    vaulta_token = persisted.get('vaulta_token')
                    if vaulta_token:
                        print(f"🔑 Retrieved token from persistent store: {vaulta_token[:20]}...")
        
        # Set token on vaulta_mcp BEFORE any operations
        if vaulta_token:
            print(f"🔐 Setting token on vaulta_mcp: {vaulta_token[:20]}...")
            vaulta_mcp.set_access_token(vaulta_token)
        else:
            print("⚠️ No token available to set on vaulta_mcp")
        
        # Get user context from Vaulta if token provided
        user_context = None
        current_token = vaulta_token
        
        if vaulta_token:
            print("👤 Fetching user context from Vaulta...")
            user_data = vaulta_mcp.client.get_current_user()
            
            if not user_data.get('error'):
                # Build user context from Vaulta data
                user_info = user_data.get('user', {})
                accounts = user_data.get('accounts', [])
                
                user_context = {
                    'email': user_info.get('email'),
                    'name': f"{user_info.get('first_name', '')} {user_info.get('last_name', '')}".strip(),
                    'phone': user_info.get('phone'),
                    'accounts': accounts,
                    'vaulta_user_id': user_info.get('id')
                }
                current_token = vaulta_token
                
                print(f"✅ User context fetched: {user_context.get('email')}")
                
                # Store token and user_context in AI session for persistence
                ai_session = ai_service.sessions.get(session_id)
                if ai_session:
                    ai_session['vaulta_token'] = vaulta_token
                    ai_session['user_context'] = user_context
                    ai_session['authenticated'] = True
                    # Persist immediately
                    ai_service._persist_session(session_id)
            else:
                # Token invalid/expired - clear it
                print(f"❌ Token invalid or expired: {user_data.get('error')}")
                current_token = None
                ai_session = ai_service.sessions.get(session_id)
                if ai_session:
                    ai_session['vaulta_token'] = None
                    ai_session['user_context'] = {}
                    ai_session['authenticated'] = False
                    ai_service._persist_session(session_id)
        else:
            # No token - check if we have persisted user context from previous session
            persisted = ai_service.store.get(session_id)
            if persisted and persisted.get('user_context', {}).get('email'):
                user_context = persisted['user_context']
                print(f"📦 Loaded user context from storage: {user_context.get('email')}")
        
        # Process chat with AI service
        response = ai_service.chat(
            session_id=session_id,
            message=message,
            user_context=user_context
        )
        
        # Check if Vaulta authentication happened - get new token
        session = ai_service.sessions.get(session_id)
        token_changed = False
        
        if session and session.get('history'):
            last_interaction = session['history'][-1]
            for tool_call in last_interaction.get('tool_calls', []):
                if tool_call['function'] in ['vaulta_verify_otp']:
                    if 'result' in tool_call and isinstance(tool_call['result'], dict):
                        result = tool_call['result']
                        # Check for both access_token and jwt_token
                        new_token = result.get('access_token') or result.get('jwt_token')
                        if new_token:
                            print(f"✅ OTP verified! Storing new access token: {new_token[:20]}...")
                            current_token = new_token
                            token_changed = True
                            session['authenticated'] = True
                            session['vaulta_token'] = new_token  # Store token in in-memory session
                            
                            # Extract user data directly from OTP verification result
                            user_data = result.get('user', {})
                            if user_data:
                                print(f"👤 Extracting user context from OTP response...")
                                user_context = {
                                    'email': user_data.get('email'),
                                    'name': f"{user_data.get('first_name', '')} {user_data.get('last_name', '')}".strip(),
                                    'phone': user_data.get('phone'),
                                    'accounts': [],  # Will be populated when needed
                                    'vaulta_user_id': user_data.get('id')
                                }
                                # Update session with user context
                                session['user_context'] = user_context
                                print(f"✅ User context saved: {user_context.get('email')}")
                            
                            # Persist everything (token + user_context) to storage
                            ai_service._persist_session(session_id)
                        break
                elif tool_call['function'] == 'vaulta_logout':
                    # Clear token and de-authenticate session
                    print("🚪 User logged out - clearing token from session")
                    current_token = None
                    session['authenticated'] = False
                    session['vaulta_token'] = None  # Clear token from in-memory session
                    user_context = None
                    token_changed = True
                    
                    # Also clear from persistent storage
                    ai_service._persist_session(session_id)
                    break
        
        # Determine conversation status
        status = determine_status(session, user_context if current_token else None)
        response['status'] = status
        
        # Always include session_id on first message, token when it changes, and always include status
        if is_first_message:
            response['session_id'] = session_id
            response['token'] = current_token
        elif token_changed:
            response['token'] = current_token
        
        return jsonify(response), 200

    except Exception as e:
        return jsonify({
            'message': 'Oops! Something went wrong. Could you try again? 😅',
            'status': 'error'
        }), 500


@chat_bp.route('/chat/history/<session_id>', methods=['GET'])
def get_history(session_id):
    """Get chat history for a session"""
    try:
        history = ai_service.get_session_history(session_id)
        
        if history is None:
            return jsonify({
                'error': 'Session not found',
                'code': 'session_not_found'
            }), 404
        
        return jsonify({
            'session_id': session_id,
            'history': history
        }), 200
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'code': 'history_error'
        }), 500


@chat_bp.route('/chat/session/<session_id>', methods=['DELETE'])
def clear_session(session_id):
    """Clear a chat session"""
    try:
        success = ai_service.clear_session(session_id)
        
        if not success:
            return jsonify({
                'error': 'Session not found',
                'code': 'session_not_found'
            }), 404
        
        return jsonify({
            'message': 'Session cleared successfully'
        }), 200
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'code': 'clear_error'
        }), 500


@chat_bp.route('/tools', methods=['GET'])
def list_tools():
    """List all available MCP tools"""
    try:
        tools = ai_service.list_available_tools()
        
        return jsonify({
            'tools': tools,
            'count': len(tools)
        }), 200
    
    except Exception as e:
        return jsonify({
            'error': str(e),
            'code': 'tools_error'
        }), 500
