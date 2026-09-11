from apps.api.app.ai.providers import _build_prompt


def test_review_response_prompt_uses_actual_review_as_primary_source() -> None:
    prompt = _build_prompt(
        "reviews.response_draft",
        {
            "rating": 2.0,
            "review": {
                "title": "Disappointing brunch",
                "body": "Our food arrived cold and the server never checked back.",
                "rating": 2.0,
            },
            "governed_facts": [
                {
                    "fact_key": "brand.approved_claims",
                    "value": "American restaurant, cocktail bar, and brunch spot in San Diego",
                    "authority": "approved",
                }
            ],
        },
    )

    assert "Disappointing brunch" in prompt
    assert "Our food arrived cold and the server never checked back." in prompt
    assert "review text is the primary source" in prompt
    assert "do not force them into the response" in prompt
    assert "Do not recite business categories" in prompt


def test_review_response_prompt_handles_rating_only_reviews() -> None:
    prompt = _build_prompt(
        "reviews.response_draft",
        {
            "rating": 5.0,
            "review": {"title": None, "body": None, "rating": 5.0},
            "governed_facts": [],
        },
    )

    assert "No written review text was provided" in prompt
    assert "Rating: 5.0/5" in prompt
