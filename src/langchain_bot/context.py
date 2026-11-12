from dataclasses import dataclass

@dataclass
class SessionContext:
    '''
    Dataclass SessionContext with user_email, conversation_id, role (default customer)
    '''
    user_email: str
    conversation_id: str
    role: str = "customer"
    