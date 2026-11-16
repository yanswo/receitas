from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from recipe.models import Receita


class Command(BaseCommand):
    help = 'Importa receitas da TheMealDB'

    @staticmethod
    def _get_json(url, params=None):
        if params:
            url = f'{url}?{urlencode(params)}'
        request = Request(url, headers={'User-Agent': 'receitas-app/1.0'})
        with urlopen(request, timeout=20) as response:
            return json.load(response)

    @staticmethod
    def _get_bytes(url):
        request = Request(url, headers={'User-Agent': 'receitas-app/1.0'})
        with urlopen(request, timeout=5) as response:
            return response.read()

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Iniciando conexao com a API...'))
        termos = ('chicken', 'beef', 'pasta', 'rice', 'fish', 'cake')
        encontrados = {}

        for termo in termos:
            try:
                dados = self._get_json(
                    'https://www.themealdb.com/api/json/v1/1/search.php',
                    {'s': termo},
                )
                for item in (dados.get('meals') or []):
                    chave = item.get('idMeal') or item.get('strMeal')
                    encontrados[chave] = item
            except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                self.stdout.write(self.style.WARNING(
                    f'Falha ao buscar {termo}: {exc}'
                ))

        self.stdout.write(
            f'Total de receitas encontradas na API: {len(encontrados)}'
        )
        salvas = 0

        total = len(encontrados)
        for indice, item in enumerate(encontrados.values(), start=1):
            nome = item.get('strMeal')
            if not nome or Receita.objects.filter(name=nome).exists():
                self.stdout.write(f'[{indice}/{total}] {nome or "Sem nome"} (ja existe)')
                continue

            self.stdout.write(f'[{indice}/{total}] Salvando {nome}...')

            ingredientes = []
            for indice in range(1, 21):
                ingrediente = (item.get(f'strIngredient{indice}') or '').strip()
                medida = (item.get(f'strMeasure{indice}') or '').strip()
                if ingrediente:
                    ingredientes.append(f'{medida} {ingrediente}'.strip())

            receita = Receita.objects.create(
                name=nome[:100],
                ingredients='\n'.join(ingredientes),
                preparationmethod=item.get('strInstructions') or '',
            )

            imagem_url = item.get('strMealThumb')
            if imagem_url:
                try:
                    imagem = self._get_bytes(imagem_url)
                    receita.fotos.save(
                        f'{item.get("idMeal", receita.pk)}.jpg',
                        ContentFile(BytesIO(imagem).getvalue()),
                        save=True,
                    )
                except (HTTPError, URLError, TimeoutError):
                    self.stdout.write(self.style.WARNING(
                        f'Imagem nao baixada para {nome}'
                    ))
            salvas += 1

        self.stdout.write(self.style.SUCCESS(
            f'{salvas} receitas novas salvas no banco de dados.'
        ))
