"""General presentation speech-act regression, not a changed quality scorer."""
import pytest
from local_cli.infrastructure.knowledge_lexical import documentary_terms


@pytest.mark.parametrize('control',[
    'Use the given markers.', 'Include citation identifiers at the end.',
    'Usa los marcadores de cita proporcionados.', 'Agrega las citas al final.',
    'Utiliza los marcadores suministrados.', 'Emite las citas después de la respuesta.'])
def test_presentation_imperative_and_object(control):
    assert documentary_terms('CACHE861 cooling medium. '+control)==('cache861','cooling','medium')


def test_factual_identifier_in_presentation_like_request_is_retained():
    assert 'canal962' in documentary_terms('Cite the CANAL962 destination source.')
