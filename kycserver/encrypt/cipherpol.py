from abc import ABC, abstractmethod
from typing import Dict, Type

class CipherPolAgent(ABC):

    name = "ParentAgent"

    @classmethod
    @abstractmethod
    def encrypt(cls, plain_text, key, **kwargs):
        raise NotImplementedError(f"{cls.name} encrypt method has not been implemented")
    
    @classmethod
    @abstractmethod
    def decrypt(cls, cipher_text, key, **kwargs):
        raise NotImplementedError(f"{cls.name} decrypt method has not been implemented")
    
    @classmethod
    @abstractmethod
    def generate_key(cls, **kwargs):
        raise NotImplementedError(f"{cls.name} key generation method has not been implemented")
    

class CipherPol:
    REGISTRY: Dict[str, Type[CipherPolAgent]] = {}

    @classmethod
    def register(cls, name: str):
        def decorator(cipher_cls: Type[CipherPolAgent]):

            if not issubclass(cipher_cls, CipherPolAgent):
                raise TypeError(
                    f"{cipher_cls.__name__} must inherit from CipherPolAgent"
                )

            if name in cls.REGISTRY:
                raise ValueError(f"Cipher '{name}' already registered")

            cls.REGISTRY[name] = cipher_cls
            return cipher_cls

        return decorator

    @classmethod
    def get(cls, name: str) -> Type[CipherPolAgent]:
        cipher = cls.REGISTRY.get(name)
        if cipher is None:
            raise ValueError(f"Unknown cipher: {name}")
        return cipher

    @classmethod
    def encrypt(cls, name: str, plaintext: str, key: str, **kwargs) -> str:
        return cls.get(name).encrypt(plaintext, key, **kwargs)

    @classmethod
    def decrypt(cls, name: str, ciphertext: str, key: str, **kwargs) -> str:
        return cls.get(name).decrypt(ciphertext, key, **kwargs)