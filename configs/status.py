"""
Status codes for conversation flow tracking
All authentication is handled by Vaulta
"""

class ConversationStatus:
    """Status codes to indicate where user is in the conversation flow"""
    
    # Authentication states (Vaulta only)
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    AUTHENTICATED = "AUTHENTICATED"
    
    # Service-specific states
    CREATING_VAULTA_ACCOUNT = "CREATING_VAULTA_ACCOUNT"
    VAULTA_ACTIVE = "VAULTA_ACTIVE"
    PROCESSING_PAYMENT = "PROCESSING_PAYMENT"
    
    # General states
    IDLE = "IDLE"
    PROCESSING = "PROCESSING"
    ERROR = "ERROR"


def determine_status(session: dict, user_context: dict = None) -> str:
    """
    Determine conversation status based on Vaulta authentication only
    
    Args:
        session: Current chat session
        user_context: User authentication context from Vaulta
    
    Returns:
        Status code string
    """
    if not session:
        return ConversationStatus.NOT_AUTHENTICATED
    
    # Check if user is authenticated with Vaulta
    if not user_context or not user_context.get('email'):
        return ConversationStatus.NOT_AUTHENTICATED
    
    # User is authenticated - check what they're doing
    if session.get('history'):
        last_interaction = session['history'][-1]
        tool_calls = last_interaction.get('tool_calls', [])
        
        # Check most recent Vaulta tool calls
        for tool_call in reversed(tool_calls):
            function_name = tool_call.get('function', '')
            
            # Vaulta operations
            if function_name == 'vaulta_create_account':
                return ConversationStatus.CREATING_VAULTA_ACCOUNT
            elif function_name == 'vaulta_create_payment':
                return ConversationStatus.PROCESSING_PAYMENT
            elif function_name.startswith('vaulta_'):
                return ConversationStatus.VAULTA_ACTIVE
    
    # Default authenticated state
    return ConversationStatus.AUTHENTICATED
