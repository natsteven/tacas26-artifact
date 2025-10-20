import org.sosy_lab.sv_benchmarks.Verifier;

public class Main {
    public static void main(String[] args) {
        String a1 = Verifier.nondetString();
        String a2 = Verifier.nondetString();
        test(a1);
        testMixed(a1, a2);
    }

    public static void test(String s1) {
        if (s1.isEmpty()) {
            System.out.println("String is empty");
        }
    }

    public static void testMixed(String s1, String s2) {
        if (!s1.contains(s2)) {
            System.out.println("s1 doesn't contain" + s2);
        }
        if (s2.isEmpty()) {
            System.out.println("s2 is empty");
        }
    }
}
