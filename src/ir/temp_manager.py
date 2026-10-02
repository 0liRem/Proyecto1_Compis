# Generación y reciclaje de variables temporales en fila


class TempManager:
    def __init__(self, prefijo="t"):
        self._prefijo = prefijo
        self._contador = 0
        self._libres = []        # stack
        self._vivos = set()      # en uso
        self.max_live = 0        
        self.total_creados = 0  

    def nuevo(self):
        if self._libres:
            nombre = self._libres.pop()
        else:
            nombre = f"{self._prefijo}{self._contador}"
            self._contador += 1
            self.total_creados += 1
        self._vivos.add(nombre)
        self.max_live = max(self.max_live, len(self._vivos))
        return nombre

    def es_temporal(self, nombre) -> bool:
        return isinstance(nombre, str) and nombre.startswith(self._prefijo) and nombre[len(self._prefijo):].isdigit()

    def liberar(self, nombre):
        if not self.es_temporal(nombre):
            return
        if nombre in self._vivos:
            self._vivos.discard(nombre)
            self._libres.append(nombre)

    def liberar_todos(self, *nombres):
        for n in nombres:
            self.liberar(n)

    def en_uso(self) -> int:
        return len(self._vivos)

    def reiniciar(self):
        self._contador = 0
        self._libres.clear()
        self._vivos.clear()
        self.max_live = 0
        self.total_creados = 0
