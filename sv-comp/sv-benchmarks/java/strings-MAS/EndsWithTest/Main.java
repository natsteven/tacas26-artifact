import org.sosy_lab.sv_benchmarks.Verifier;

public class Main {
    public static void main(String[] args) {
        String a1 = Verifier.nondetString();
        String a2 = Verifier.nondetString();
        testSym(a1, a2);
        testConc(a1);
    }

    public static void testSym(String s1, String s2) {
        if (s1.endsWith(s2)) {
            System.out.println("s1 ends with s2");
        } else if (s2.endsWith(s1)) {
            System.out.println("s2 ends with s1");
        } else {
            System.out.println("s1 does not start with s2 and s2 does not start with s1");
        }
    }

    public static void testConc(String s2) {
        String s3 = "World";
        if (s2.endsWith(s3)) {
            System.out.println("s2 ends with World");
        } else {
            System.out.println("s2 does not ends with World");
        }
    }
}
