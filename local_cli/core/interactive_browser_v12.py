"""V1.2 internal baseline descriptor. Neither a grant nor a product snapshot.

Page data and Controlled Fetch evidence cannot upgrade this network claim.
Actions, transfers and productive integration require their later V1.2 gates.
"""
from dataclasses import dataclass


INTERACTIVE_BROWSER_CAPABILITY_ID = 'INTERACTIVE_BROWSER_V1_2'


@dataclass(frozen=True)
class InteractiveBrowserBaselineMetadata:
    """Fixed host description; construction never authorizes a browser action."""

    def to_dict(self):
        return dict(capabilityId=INTERACTIVE_BROWSER_CAPABILITY_ID,
                    adapter='WEBVIEW2', networkIsolation='NOT_PROVIDED',
                    controlClass='HOST_UNISOLATED',
                    productiveAvailability='NOT_ENABLED',
                    pageContentTrust='UNTRUSTED_DATA',
                    externalProtocolPolicy='DENY_ALL', popupPolicy='DENY_ALL')

    @classmethod
    def from_dict(cls, data):
        expected = cls().to_dict()
        if type(data) is not dict or data != expected:
            raise ValueError('INVALID_INTERACTIVE_BROWSER_V12_METADATA')
        return cls()
