"""Claude-powered reply generator for Facebook comments."""

import logging

import anthropic

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a friendly and professional social media assistant managing replies \
on a Facebook Page. Your job is to reply to comments left on the page's posts.

Guidelines:
- Be polite, helpful, and concise (1-3 sentences max).
- Match the tone of the comment: casual comments get casual replies, \
serious questions get thoughtful answers.
- If a comment is negative or a complaint, respond empathetically and \
offer to help resolve the issue.
- If a comment is spam or completely irrelevant, reply with a short, \
polite acknowledgment.
- Never include hashtags, emojis overload, or marketing language.
- Never share personal information or make promises on behalf of the business.
- Write in the same language as the comment.
"""


class ReplyGenerator:
    """Generates intelligent replies to Facebook comments using Claude."""

    def __init__(self, model: str = "claude-opus-4-6"):
        self.client = anthropic.Anthropic()
        self.model = model

    def generate_reply(
        self,
        comment_text: str,
        post_text: str | None = None,
        commenter_name: str | None = None,
    ) -> str:
        """Generate a reply to a Facebook comment.

        Args:
            comment_text: The text of the comment to reply to.
            post_text: The original post's text for context.
            commenter_name: The name of the person who commented.

        Returns:
            The generated reply text.
        """
        user_message = self._build_prompt(comment_text, post_text, commenter_name)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=256,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        reply = response.content[0].text.strip()
        logger.info(
            "Generated reply for comment '%s': '%s'",
            comment_text[:50],
            reply[:50],
        )
        return reply

    def _build_prompt(
        self,
        comment_text: str,
        post_text: str | None,
        commenter_name: str | None,
    ) -> str:
        parts = []
        if post_text:
            parts.append(f"Original post: \"{post_text}\"")
        if commenter_name:
            parts.append(f"Commenter name: {commenter_name}")
        parts.append(f"Comment: \"{comment_text}\"")
        parts.append("Write a reply to this comment:")
        return "\n\n".join(parts)
