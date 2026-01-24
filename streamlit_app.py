import streamlit as st
import requests
import json
import uuid
from datetime import datetime

# Configuration
AGENT_URL = "http://46.250.237.184:8000/agents/houpe-agent/runs"

# Initialize session state
if 'sessions' not in st.session_state:
    st.session_state.sessions = {}
if 'current_session' not in st.session_state:
    st.session_state.current_session = None
if 'session_counter' not in st.session_state:
    st.session_state.session_counter = 1

def create_new_session():
    """Create a new chat session"""
    session_id = str(st.session_state.session_counter)
    st.session_state.session_counter += 1
    
    st.session_state.sessions[session_id] = {
        'id': session_id,
        'name': f"Chat {session_id}",
        'messages': [],
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M")
    }
    st.session_state.current_session = session_id
    return session_id

def send_message(message, session_id):
    """Send message to Houpe Agent"""
    try:
        # Form data untuk multipart/form-data
        form_data = {
            "message": (None, message),
            "session_id": (None, session_id),
            "user_id": (None, "666"),  # bisa diganti sesuai kebutuhan
            "stream": (None, "false")
        }
        
        response = requests.post(
            AGENT_URL,
            files=form_data,
            headers={"accept": "application/json"},
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "error": True,
                "status_code": response.status_code,
                "message": f"Error: {response.status_code}"
            }
            
    except requests.exceptions.Timeout:
        return {"error": True, "message": "Request timeout"}
    except requests.exceptions.RequestException as e:
        return {"error": True, "message": str(e)}

# Page config
st.set_page_config(
    page_title="Houpe Agent Chat",
    page_icon="💬",
    layout="wide"
)

# Sidebar - Session Management
with st.sidebar:
    st.title("💬 Chat Sessions")
    
    # New Session Button
    if st.button("➕ New Session", use_container_width=True, type="primary"):
        create_new_session()
        st.rerun()
    
    st.divider()
    
    # List of sessions
    if st.session_state.sessions:
        st.subheader("Your Sessions")
        for session_id, session in st.session_state.sessions.items():
            col1, col2 = st.columns([4, 1])
            
            with col1:
                # Button untuk switch session
                if st.button(
                    f"📝 {session['name']}", 
                    key=f"session_{session_id}",
                    use_container_width=True,
                    type="secondary" if st.session_state.current_session != session_id else "primary"
                ):
                    st.session_state.current_session = session_id
                    st.rerun()
            
            with col2:
                # Delete button
                if st.button("🗑️", key=f"del_{session_id}"):
                    del st.session_state.sessions[session_id]
                    if st.session_state.current_session == session_id:
                        st.session_state.current_session = None
                    st.rerun()
            
            # Show created time
            st.caption(f"Created: {session['created_at']}")
            st.divider()
    else:
        st.info("No sessions yet. Click 'New Session' to start!")
    
    # Info section
    st.divider()
    st.caption("🤖 Houpe Agent")
    st.caption("Powered by AgentOps")

# Main Chat Interface
if st.session_state.current_session is None:
    # Welcome screen
    st.title("👋 Welcome to Houpe Agent Chat")
    st.write("Click **New Session** in the sidebar to start chatting!")
    
    st.info("💡 Houpe Agent adalah customer support yang siap membantu Anda dengan informasi tentang Houpe.id")
    
else:
    current_session = st.session_state.sessions[st.session_state.current_session]
    
    # Header
    col1, col2 = st.columns([6, 1])
    with col1:
        st.title(f"💬 {current_session['name']}")
    with col2:
        # Rename session
        if st.button("✏️ Rename"):
            st.session_state.rename_mode = True
    
    # Rename modal (simple version)
    if 'rename_mode' in st.session_state and st.session_state.rename_mode:
        new_name = st.text_input("New session name:", value=current_session['name'])
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Save"):
                current_session['name'] = new_name
                st.session_state.rename_mode = False
                st.rerun()
        with col2:
            if st.button("Cancel"):
                st.session_state.rename_mode = False
                st.rerun()
    
    st.divider()
    
    # Chat messages container
    chat_container = st.container()
    
    with chat_container:
        # Display chat history
        for msg in current_session['messages']:
            if msg['role'] == 'user':
                with st.chat_message("user", avatar="👤"):
                    st.write(msg['content'])
            else:
                with st.chat_message("assistant", avatar="🤖"):
                    st.markdown(msg['content'])
                    
                    # Show metrics if available
                    if 'metrics' in msg:
                        with st.expander("📊 Response Metrics"):
                            metrics = msg['metrics']
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Total Tokens", metrics.get('total_tokens', 'N/A'))
                            with col2:
                                st.metric("Duration", f"{metrics.get('duration', 0):.2f}s")
                            with col3:
                                st.metric("Model", msg.get('model', 'N/A'))
    
    # Chat input
    user_input = st.chat_input("Type your message here...")
    
    if user_input:
        # Add user message to chat
        current_session['messages'].append({
            'role': 'user',
            'content': user_input
        })
        
        # Display user message
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.write(user_input)
        
        # Show loading spinner
        with chat_container:
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Agent is thinking..."):
                    # Send to agent
                    response = send_message(user_input, st.session_state.current_session)
                    
                    if 'error' in response:
                        st.error(f"❌ {response['message']}")
                        assistant_message = f"Sorry, there was an error: {response['message']}"
                    else:
                        # Extract response content
                        assistant_message = response.get('content', 'No response')
                        
                        # Display response
                        st.markdown(assistant_message)
                        
                        # Show metrics
                        if 'metrics' in response:
                            with st.expander("📊 Response Metrics"):
                                metrics = response['metrics']
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Total Tokens", metrics.get('total_tokens', 'N/A'))
                                with col2:
                                    st.metric("Duration", f"{metrics.get('duration', 0):.2f}s")
                                with col3:
                                    st.metric("Model", response.get('model', 'N/A'))
                        
                        # Add assistant message to chat
                        current_session['messages'].append({
                            'role': 'assistant',
                            'content': assistant_message,
                            'metrics': response.get('metrics', {}),
                            'model': response.get('model', '')
                        })
        
        st.rerun()

# Footer
st.divider()
st.caption("Made with ❤️ for Houpe.id | Powered by Streamlit")