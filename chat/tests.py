from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from . import views


class MultiDebuggerModelRoutingTests(SimpleTestCase):
    def test_uncensored_reply_scopes_roast_style_to_latest_message(self):
        create = MagicMock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="A playful roast.")
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=4, completion_tokens=3),
            )
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=create,
                )
            )
        )

        with patch.object(views, "get_uncensored_client", return_value=client):
            response = views._uncensored_chat_reply(
                [
                    {"role": "user", "content": "Let's have a roast battle. Roast me."},
                    {"role": "assistant", "content": "A sharp roast."},
                    {"role": "user", "content": "Hi bro"},
                ]
            )

        self.assertEqual(response, ("A playful roast.", 4, 3))
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["model"], views.UNCENSORED_MODEL)
        request_messages = kwargs["messages"]
        self.assertEqual(request_messages[0]["content"], "Let's have a roast battle. Roast me.")
        self.assertEqual(request_messages[1]["content"], "A sharp roast.")
        self.assertEqual(request_messages[2]["role"], "system")
        system_prompt = request_messages[2]["content"]
        self.assertIn("Follow the user's latest request and requested tone", system_prompt)
        self.assertIn("lively, emotionally expressive chat partner", system_prompt)
        self.assertIn("For a first direct insult, show brief genuine-sounding surprise", system_prompt)
        self.assertIn("let the irritation build", system_prompt)
        self.assertIn("use occasional mild profanity", system_prompt)
        self.assertIn("reset to warm and friendly when they do", system_prompt)
        self.assertIn("A plain greeting gets a friendly reply", system_prompt)
        self.assertIn("trade sharp, funny roasts", system_prompt)
        self.assertIn("regardless of earlier banter", system_prompt)
        self.assertEqual(request_messages[3]["content"], "Hi bro")

    def test_uncensored_reply_keeps_explicit_roast_request_as_current_turn(self):
        create = MagicMock(
            return_value=SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content="A playful roast.")
                    )
                ],
                usage=SimpleNamespace(prompt_tokens=4, completion_tokens=3),
            )
        )
        client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create))
        )

        with patch.object(views, "get_uncensored_client", return_value=client):
            views._uncensored_chat_reply(
                [
                    {"role": "assistant", "content": "Hey, good to see you."},
                    {"role": "user", "content": "Roast me."},
                ]
            )

        request_messages = create.call_args.kwargs["messages"]
        self.assertEqual(request_messages[-2]["role"], "system")
        self.assertEqual(request_messages[-1]["content"], "Roast me.")
        self.assertIn(
            "trade sharp, funny roasts",
            request_messages[-2]["content"],
        )

    def test_uncensored_client_reuses_verified_openrouter_client(self):
        self.assertIs(views.get_uncensored_client(), views.openrouter_client)

    def test_regular_mistral_client_uses_openrouter(self):
        self.assertEqual(
            str(views.openrouter_client.base_url).rstrip("/"),
            "https://openrouter.ai/api/v1",
        )
        self.assertEqual(views.REGULAR_MODEL, views.DEBUG_MISTRAL_MODEL)

    def test_legacy_regular_model_maps_to_supported_openrouter_model(self):
        self.assertEqual(
            views._resolve_regular_model("mistral-medium-latest"),
            "mistralai/mistral-medium-3",
        )

    def test_uncensored_model_maps_legacy_free_route_to_supported_model(self):
        self.assertEqual(
            views._resolve_uncensored_model(
                "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"
            ),
            "cognitivecomputations/dolphin-mistral-24b-venice-edition",
        )
        self.assertEqual(
            views._resolve_uncensored_model(
                "cognitivecomputations/dolphin-mistral-24b-venice-edition"
            ),
            "cognitivecomputations/dolphin-mistral-24b-venice-edition",
        )

    def test_openrouter_tls_verification_uses_custom_ca_bundle_when_configured(self):
        with (
            patch.object(views.ssl, "create_default_context") as create_context,
            patch.object(views.httpx, "Client") as httpx_client,
        ):
            views._create_openrouter_http_client("C:/certs/proxy-root.pem")

        create_context.return_value.load_verify_locations.assert_called_once_with(
            cafile="C:/certs/proxy-root.pem",
        )
        httpx_client.assert_called_once_with(
            verify=create_context.return_value,
        )

    def test_openrouter_tls_verification_stays_enabled_by_default(self):
        with (
            patch.object(views.ssl, "create_default_context") as create_context,
            patch.object(views.httpx, "Client") as httpx_client,
        ):
            views._create_openrouter_http_client()

        create_context.return_value.load_verify_locations.assert_not_called()
        httpx_client.assert_called_once_with(verify=create_context.return_value)

    def test_free_tier_keeps_its_existing_models(self):
        message = "Trace the cause of this reproducible exception."
        result = ("analysis", 12, 8)

        with (
            patch.object(views, "_agent_mistral_logic_analyst", return_value=result) as logic_agent,
            patch.object(views, "_agent_mistral_syntax_inspector", return_value=result),
            patch.object(views, "_agent_gemini_perf_security", return_value=result),
        ):
            _, usage = views._run_agents_parallel("free", message)

        logic_agent.assert_called_once_with(message, views.DEBUG_MISTRAL_MODEL)
        self.assertEqual(usage["logic_analyst"][0], views.DEBUG_MISTRAL_MODEL)
        self.assertEqual(usage["syntax_inspector"][0], views.REGULAR_MODEL)
        self.assertEqual(usage["perf_security_auditor"][0], views.GEMINI_FREE_MODEL)

    def test_premium_specialists_use_role_specific_models(self):
        message = "Trace the cause of this reproducible exception."
        result = ("analysis", 12, 8)

        with (
            patch.object(views, "DEBUG_PREMIUM_LOGIC_MODEL", "google/gemini-4-argon"),
            patch.object(views, "DEBUG_PREMIUM_SYNTAX_MODEL", "openai/gpt-5.4"),
            patch.object(views, "DEBUG_PREMIUM_PERF_MODEL", "anthropic/claude-opus-4.7"),
            patch.object(views, "_agent_premium_logic_analyst", return_value=result) as logic_agent,
            patch.object(views, "_agent_premium_syntax_inspector", return_value=result) as syntax_agent,
            patch.object(views, "_agent_premium_perf_security", return_value=result) as audit_agent,
        ):
            _, usage = views._run_agents_parallel("premium", message)

        for agent in (logic_agent, syntax_agent, audit_agent):
            agent.assert_called_once_with(message)
        self.assertEqual(usage["logic_analyst"][0], "google/gemini-4-argon")
        self.assertEqual(usage["syntax_inspector"][0], "openai/gpt-5.4")
        self.assertEqual(usage["perf_security_auditor"][0], "anthropic/claude-opus-4.7")

    def test_premium_synthesizer_uses_sonnet(self):
        result = ("synthesis", 12, 8)
        with (
            patch.object(views, "DEBUG_PREMIUM_SYNTH_MODEL", "anthropic/claude-sonnet-4.6"),
            patch.object(views, "_agent_openrouter_specialist", return_value=result) as specialist,
        ):
            response = views._agent_synthesizer("input", "logic", "syntax", "audit")

        self.assertEqual(response, result)
        self.assertEqual(
            specialist.call_args.kwargs["model"],
            "anthropic/claude-sonnet-4.6",
        )
        self.assertEqual(specialist.call_args.kwargs["max_tokens"], 4096)

    def test_premium_model_pricing_matches_openrouter_ids(self):
        self.assertEqual(
            views._get_model_pricing("anthropic/claude-opus-4.7"),
            {"input": 5.00, "output": 25.00},
        )
        self.assertEqual(
            views._get_model_pricing("anthropic/claude-sonnet-4.6"),
            {"input": 3.00, "output": 15.00},
        )
