# ============================================================================
# SUPPRESS_SYSTEM_MESSAGES CONFIGURATION
# ============================================================================
# 
# Use this configuration to prevent internal system messages from leaking
# to end customers in customer-facing deployments (WhatsApp, Discord, etc.).
#
# When suppress_system_messages: true, the following messages are suppressed:
#   • "📬 No home channel is set for..." (configuration warnings)
#   • "✨ Session reset! Starting fresh." (session reset notifications)
#   • "⚠️ Dangerous command requires approval:" (approval prompts)
#   • Assistant narration like "Perfeito! Enviei as mensagens..."
#
# IMPORTANT: The session still resets, commands are still auto-denied, and
# internal state is updated normally — only the customer notification is
# suppressed. All suppressed messages are logged to gateway.log.
#
# ============================================================================

display:
  platforms:
    # --------------------------------------------------------------------------
    # WhatsApp Configuration (Tchê Gourmet example)
    # --------------------------------------------------------------------------
    whatsapp:
      # Suppress internal system messages from being delivered to customers
      suppress_system_messages: true
      
      # Optional: Fine-grained control (if you want to suppress only specific types)
      # suppress_session_reset: true      # Don't notify about session resets
      # suppress_approval_prompts: true   # Auto-deny dangerous commands silently
      # suppress_config_warnings: true    # Don't show "No home channel" warnings
      
      # Delivery mode for operational notices
      notice_delivery: private  # or "public"
      
      # Profile-specific settings
      profile: tete
      
    # --------------------------------------------------------------------------
    # Discord Configuration
    # --------------------------------------------------------------------------
    discord:
      suppress_system_messages: true
      notice_delivery: private
      
    # --------------------------------------------------------------------------
    # Telegram Configuration
    # --------------------------------------------------------------------------
    telegram:
      suppress_system_messages: false  # Keep true for internal testing
      notice_delivery: public
      
    # --------------------------------------------------------------------------
    # Slack Configuration
    # --------------------------------------------------------------------------
    slack:
      suppress_system_messages: true
      notice_delivery: private

# ============================================================================
# RECOMMENDED SETUP FOR CUSTOMER-FACING DEPLOYMENTS
# ============================================================================
#
# For production deployments where customers interact via WhatsApp/Discord:
#
# 1. Set suppress_system_messages: true for customer-facing platforms
# 2. Keep suppress_system_messages: false for admin platforms (e.g., your
#    personal Telegram where you want to see all system messages)
# 3. Monitor gateway.log for suppressed messages (logged at DEBUG/WARNING level)
# 4. Consider setting up a separate admin channel for system notifications
#
# Example: Tchê Gourmet Production Setup
# ---------------------------------------
# - WhatsApp (customers): suppress_system_messages: true
# - Telegram (Marcon/Thay): suppress_system_messages: false (admin channel)
#
# This way, customers see only food-related messages, while admins receive
# full system notifications for debugging and monitoring.
#
# ============================================================================
# LOGGING BEHAVIOR
# ============================================================================
#
# All suppressed messages are logged to gateway.log:
#
#   [whatsapp] Suppressed internal notice (customer-facing): 📬 No home channel...
#   [whatsapp] Suppressed session reset notification (customer-facing)
#   [whatsapp] Dangerous command auto-denied (customer-facing, suppress_system_messages=true): rm -rf /tmp — Reason: ...
#
# To view suppressed messages in real-time:
#   hermes logs --follow --level DEBUG --grep "Suppressed"
#
# ============================================================================
