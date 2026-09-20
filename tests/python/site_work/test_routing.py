from apps.api.app.site_work.routing import is_technical_site_change


def test_technical_site_change_classifier_catches_template_and_h1_work() -> None:
    assert is_technical_site_change(
        "content.add_missing_h1",
        "publish_content_asset",
        "Add the missing H1 to the blog index template.",
    )


def test_technical_site_change_classifier_keeps_editorial_content_in_content() -> None:
    assert not is_technical_site_change(
        "content.create_local_guide",
        "publish_content_asset",
        "Publish a substantive Little Italy dining guide for non-branded search intent.",
    )
