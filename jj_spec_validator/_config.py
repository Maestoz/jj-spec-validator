class Config:
    # service
    MAIN_DIRECTORY = "spec_validator"
    GET_SPEC_TIMEOUT = 30.0

    # interface
    OUTPUT_FUNCTION = None  # can be used for custom output func

    # params
    IS_RAISES = False
    IS_STRICT = False
    SKIP_IF_FAILED_TO_GET_SPEC = False
