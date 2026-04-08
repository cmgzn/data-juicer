from typing import Dict


class ConfigValidationError(Exception):
    """Custom exception for validation errors"""

    pass


class ConfigValidator:
    """Mixin class for configuration validation"""

    # Define validation rules for each strategy type.
    # Subclasses override this with their own rules.
    CONFIG_VALIDATION_RULES = {
        "required_fields": [],  # Fields that must be present
        "optional_fields": [],  # Fields that are optional
        "field_types": {},  # Expected types for fields
        "custom_validators": {},  # Custom validation functions
    }

    def _get_merged_rules(self) -> Dict:
        """Merge BASE_CONFIG_RULES (if defined) with CONFIG_VALIDATION_RULES.

        The base rules provide common fields (e.g. ``weight``, ``type``)
        that are valid for all strategies.  Subclass rules add
        strategy-specific fields.  The merge is additive: lists are
        concatenated (deduplicated) and dicts are shallow-merged with
        subclass values taking precedence for the same key.

        Returns:
            A merged rules dict with the same structure as
            ``CONFIG_VALIDATION_RULES``.
        """
        base_rules = getattr(self, "BASE_CONFIG_RULES", None)
        sub_rules = self.CONFIG_VALIDATION_RULES

        if not base_rules:
            return sub_rules

        def _merge_lists(base_list, sub_list):
            """Concatenate two lists, preserving order and deduplicating."""
            seen = set(sub_list)
            merged = list(sub_list)
            for item in base_list:
                if item not in seen:
                    merged.append(item)
                    seen.add(item)
            return merged

        def _merge_dicts(base_dict, sub_dict):
            """Shallow-merge two dicts; sub_dict values win on conflict."""
            merged = dict(base_dict)
            merged.update(sub_dict)
            return merged

        return {
            "required_fields": _merge_lists(
                base_rules.get("required_fields", []),
                sub_rules.get("required_fields", []),
            ),
            "optional_fields": _merge_lists(
                base_rules.get("optional_fields", []),
                sub_rules.get("optional_fields", []),
            ),
            "field_types": _merge_dicts(
                base_rules.get("field_types", {}),
                sub_rules.get("field_types", {}),
            ),
            "custom_validators": _merge_dicts(
                base_rules.get("custom_validators", {}),
                sub_rules.get("custom_validators", {}),
            ),
        }

    def validate_config(self, ds_config: Dict) -> None:
        """
        Validate the configuration dictionary.

        Merges ``BASE_CONFIG_RULES`` (common fields from the base class)
        with the subclass ``CONFIG_VALIDATION_RULES`` before validation.

        Args:
            ds_config: Configuration dictionary to validate

        Raises:
            ConfigValidationError: If validation fails
        """
        rules = self._get_merged_rules()

        # Check required fields
        missing_fields = [field for field in rules["required_fields"] if field not in ds_config]
        if missing_fields:
            raise ConfigValidationError(f"Missing required fields: {', '.join(missing_fields)}")

        # Optional fields
        # no need for any special checks

        # Check field types
        for field, expected_type in rules["field_types"].items():
            if field in ds_config:
                value = ds_config[field]
                if not isinstance(value, expected_type):
                    if isinstance(expected_type, type):
                        type_name = expected_type.__name__
                    elif isinstance(expected_type, tuple):
                        type_name = " | ".join(t.__name__ for t in expected_type)
                    else:
                        type_name = str(expected_type)
                    raise ConfigValidationError(
                        f"Field '{field}' must be of " f"type '{type_name}', " f"got '{type(value).__name__}'"
                    )

        # Run custom validators
        for field, validator in rules["custom_validators"].items():
            if field in ds_config:
                try:
                    validator(ds_config[field])
                except Exception as e:
                    raise ConfigValidationError(f"Validation failed for field '{field}': {str(e)}")
